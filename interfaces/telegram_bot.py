"""
Telegram interface for GawdBot.

Patterns borrowed from claude-telegram-relay:
- Message queue for sequential processing (no race conditions)
- Rate limiting
- Long response chunking
- Voice transcription via faster-whisper
"""

from __future__ import annotations
import asyncio
import os
import subprocess
import tempfile
from collections import deque
from typing import Callable

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import config
from core import memory
from core.agent import chat, stream_chat
from core.self_evolve import propose_improvement

# ── Authorization ─────────────────────────────────────────────────────────────

def _authorized(user_id: int) -> bool:
    return config.TELEGRAM_USER_ID == 0 or user_id == config.TELEGRAM_USER_ID


# ── Rate limiter ──────────────────────────────────────────────────────────────

_rate_buckets: dict[int, list] = {}
_RATE_LIMIT = 15
_RATE_WINDOW = 60.0


def _check_rate(user_id: int) -> bool:
    import time
    now = time.monotonic()
    bucket = _rate_buckets.setdefault(user_id, [])
    _rate_buckets[user_id] = [t for t in bucket if now - t < _RATE_WINDOW]
    if len(_rate_buckets[user_id]) >= _RATE_LIMIT:
        return False
    _rate_buckets[user_id].append(now)
    return True


# ── Message queue (sequential processing per user) ────────────────────────────

_queue: asyncio.Queue = asyncio.Queue()


async def _worker() -> None:
    while True:
        task = await _queue.get()
        try:
            await task()
        except Exception as e:
            print(f"[Telegram] Queue worker error: {e}")
        finally:
            _queue.task_done()


# ── Response sender (handles Telegram's 4096 char limit) ─────────────────────

async def _send(update: Update, text: str) -> None:
    MAX = 4000
    if len(text) <= MAX:
        await update.message.reply_text(text)
        return
    remaining = text
    while remaining:
        if len(remaining) <= MAX:
            await update.message.reply_text(remaining)
            break
        split = remaining.rfind("\n\n", 0, MAX)
        if split == -1:
            split = remaining.rfind("\n", 0, MAX)
        if split == -1:
            split = remaining.rfind(" ", 0, MAX)
        if split == -1:
            split = MAX
        await update.message.reply_text(remaining[:split])
        remaining = remaining[split:].lstrip()


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "GawdBot online.\n\n"
        "I can chat, write and commit code, search memory, and improve myself.\n"
        "Use /help to see commands."
    )


async def _cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "/start — Greeting\n"
        "/help — This message\n"
        "/evolve <request> — Ask me to improve my own code\n"
        "/memory <query> — Search persistent memory\n"
        "\nOr just send a message — text or voice."
    )


async def _cmd_evolve(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update.effective_user.id):
        return
    request = " ".join(ctx.args or [])
    if not request:
        await update.message.reply_text("Usage: /evolve <what to improve>")
        return
    await update.message.reply_text("Starting self-improvement cycle...")

    async def _run():
        result = await propose_improvement(request, interface="telegram")
        await _send(update, result)

    await _queue.put(_run)


async def _cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update.effective_user.id):
        return
    query = " ".join(ctx.args or [])
    if not query:
        await update.message.reply_text("Usage: /memory <search query>")
        return
    results = await memory.search_memory(query)
    if not results:
        await update.message.reply_text("No memories found.")
        return
    lines = [f"[{r['category']}] {r['content']}" for r in results]
    await _send(update, "\n\n".join(lines))


async def _stream_reply(update: Update, text: str) -> None:
    """
    Stream agent response into a live Telegram message.
    Edits the placeholder every ~300ms to show tokens as they arrive.
    Falls back to _send() for long responses (>4000 chars).
    """
    placeholder = await update.message.reply_text("…")
    buf = ""
    last_edit = asyncio.get_event_loop().time()
    EDIT_INTERVAL = 0.3  # seconds between edits — avoids Telegram flood-wait

    async for chunk in stream_chat(text, interface="telegram"):
        buf += chunk
        now = asyncio.get_event_loop().time()
        if now - last_edit >= EDIT_INTERVAL and len(buf) <= 4000:
            try:
                await placeholder.edit_text(buf)
                last_edit = now
            except Exception:
                pass  # edit failed (no change, flood) — ignore

    if not buf:
        await placeholder.edit_text("(no response)")
        return

    if len(buf) <= 4000:
        # Final edit with complete text
        try:
            await placeholder.edit_text(buf)
        except Exception:
            pass
    else:
        # Too long for one message — delete placeholder, chunk it out
        try:
            await placeholder.delete()
        except Exception:
            pass
        await _send(update, buf)


async def _handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update.effective_user.id):
        return
    if not _check_rate(update.effective_user.id):
        await update.message.reply_text("Slow down a bit.")
        return
    text = update.message.text

    async def _run():
        await update.message.chat.send_action("typing")
        await _stream_reply(update, text)

    await _queue.put(_run)


async def _handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Transcribe voice message then route through agent."""
    if not _authorized(update.effective_user.id):
        return
    if not _check_rate(update.effective_user.id):
        await update.message.reply_text("Slow down a bit.")
        return

    async def _run():
        await update.message.chat.send_action("typing")

        voice_file = await update.message.voice.get_file()
        ogg_bytes = await voice_file.download_as_bytearray()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(ogg_bytes)
            ogg_path = f.name
        wav_path = ogg_path.replace(".ogg", ".wav")

        try:
            subprocess.run(
                ["ffmpeg", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path, "-y", "-loglevel", "error"],
                check=True,
            )
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()
        finally:
            os.unlink(ogg_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)

        from core.voice import transcribe
        text = transcribe(wav_bytes)
        if not text:
            await update.message.reply_text("Couldn't transcribe that.")
            return

        await update.message.reply_text(f"_{text}_", parse_mode="Markdown")
        await _stream_reply(update, text)

    await _queue.put(_run)


# ── App factory ───────────────────────────────────────────────────────────────

def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("evolve", _cmd_evolve))
    app.add_handler(CommandHandler("memory", _cmd_memory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
    app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
    return app


async def run(app: Application) -> None:
    asyncio.create_task(_worker())
    await app.initialize()
    await app.bot.set_my_commands([
        BotCommand("start", "Greet GawdBot"),
        BotCommand("help", "Show commands"),
        BotCommand("evolve", "Self-improvement cycle"),
        BotCommand("memory", "Search memory"),
    ])
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("[Telegram] Bot started.")
    await asyncio.Event().wait()
