"""
GawdBot — entry point.

Starts:
  1. Persistent memory DB init
  2. Voice wake-word loop (daemon thread, shares main event loop via run_coroutine_threadsafe)
  3. Telegram bot (async, main event loop)
"""

import asyncio
import sys
import threading

import config
from core import memory
from core.agent import chat as agent_chat


async def _on_speech(text: str) -> str:
    """Called from the voice thread — runs on the main event loop."""
    return await agent_chat(text, interface="voice")


async def main() -> None:
    print("GawdBot starting...")

    memory.init_db()

    main_loop = asyncio.get_running_loop()

    if config.VOICE_ENABLED:
        from core.voice import run_voice_loop

        def _voice_thread():
            run_voice_loop(_on_speech, main_loop)

        t = threading.Thread(target=_voice_thread, name="voice", daemon=True)
        t.start()
        print("[Voice] Thread started.")
    else:
        print("[Voice] Disabled (set VOICE_ENABLED=true to enable).")

    tasks = []

    if config.WEBHOOK_ENABLED:
        from interfaces.webhook_server import run as run_webhook
        tasks.append(asyncio.create_task(run_webhook()))

    if config.TELEGRAM_BOT_TOKEN:
        from interfaces.telegram_bot import build_app, run as run_telegram
        app = build_app()
        tasks.append(asyncio.create_task(run_telegram(app)))
    else:
        print("[Telegram] No token set. Set TELEGRAM_BOT_TOKEN in .env to enable.")

    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("No interfaces active. Set TELEGRAM_BOT_TOKEN in .env.")
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGawdBot shutting down.")
        sys.exit(0)
