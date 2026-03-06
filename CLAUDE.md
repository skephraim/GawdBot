# GawdBot — Architecture Reference

Read this file before modifying any source code. It describes the full project structure, design decisions, and rules for self-improvement.

## What GawdBot Is

GawdBot is a self-evolving AI assistant combining:
- **Voice interface**: Wake word → STT → LLM → TTS (runs locally on NVIDIA GPU)
- **Telegram interface**: Text and voice messages, with message queue and rate limiting
- **Webhook server**: HTTP endpoints for external triggers and text embeddings
- **PC control**: Mouse, keyboard, windows, clipboard, screenshots via pyautogui
- **Persistent memory**: SQLite with embedding-based semantic search (no vector DB needed)
- **Coding agent**: Reads/writes files, runs commands, commits to git, creates GitHub PRs
- **Self-evolution**: Modifies own source code on a branch, optionally creates a PR for review

## Directory Structure

```
gawdbot/
├── main.py                      # Entry point — starts voice thread + webhook + Telegram
├── config.py                    # All configuration from .env
├── CLAUDE.md                    # This file
│
├── core/
│   ├── llm.py                   # OpenAI-compatible client (NVIDIA NIM or Ollama)
│   ├── memory.py                # SQLite persistent memory + cosine similarity search
│   ├── agent.py                 # Agentic loop: tool definitions + execution + chat()
│   ├── voice.py                 # Wake word (openwakeword), STT (faster-whisper), TTS (piper)
│   └── self_evolve.py           # Self-improvement workflow
│
├── tools/
│   ├── git_tools.py             # Git: status, diff, commit, branch, push, create PR
│   ├── code_tools.py            # File read/write, command execution, list project files
│   └── pc_control.py            # Mouse, keyboard, windows, clipboard, screenshot
│
├── interfaces/
│   ├── telegram_bot.py          # Telegram bot with message queue + rate limiting
│   └── webhook_server.py        # aiohttp HTTP server: /webhook, /webhook/embed, /health
│
└── data/
    └── memory.db                # SQLite database (gitignored)
```

## LLM Backend

`core/llm.py` — single `AsyncOpenAI` client, base URL switches by `LLM_BACKEND`:
- `"nvidia"`: NVIDIA NIM at `https://integrate.api.nvidia.com/v1`
- `"ollama"`: Local Ollama at `http://localhost:11434/v1`

Both use identical OpenAI-compatible API. Add new providers by extending `_get_client()`, `chat_model()`, and `embed_model()`.

NVIDIA NIM embeddings require `input_type`: `"passage"` for storage, `"query"` for search.

## Tool System

Tools are defined in `core/agent.py` as OpenAI function-calling schemas in the `TOOLS` list. Execution is in `_execute_tool()`. The agentic loop in `chat()` runs until the model stops calling tools or hits iteration 15.

**Adding a new tool:**
1. Add a schema dict to the `TOOLS` list
2. Add an execution branch in `_execute_tool()`
3. Implement the underlying function in `tools/` if complex

## Memory

`core/memory.py` — two SQLite tables:
- `memories`: Long-term facts, goals, code notes. Semantically searched via embeddings stored as JSON arrays. Cosine similarity computed in Python with numpy.
- `conversations`: Recent chat history, retrieved by recency.

Embeddings are always stored as JSON-serialized float arrays. No external vector DB.

## Concurrent Architecture

`main.py` runs three concurrent components:
1. **Voice loop**: `threading.Thread` (daemon) — blocking pyaudio loop. Submits agent calls to the main asyncio loop via `asyncio.run_coroutine_threadsafe`.
2. **Webhook server**: `asyncio.Task` — aiohttp on `WEBHOOK_PORT`
3. **Telegram bot**: `asyncio.Task` — python-telegram-bot polling

Telegram uses an `asyncio.Queue` to serialize message processing per conversation, preventing race conditions on the memory DB.

## Self-Evolution Rules

When improving yourself:
1. Read this file (CLAUDE.md) first
2. Read the specific files you need to change
3. Make **minimal, targeted changes** — do not refactor unrelated code
4. Verify syntax: `python -m py_compile <file>`
5. Commit to the current branch (already created) — never checkout main
6. Write a clear commit message and return a human-readable summary
7. The TOOLS list and `_execute_tool()` function are the agent's API — changing them may break all interfaces

## Security Notes

- `.env` and `.git` are write-protected in `tools/code_tools.py`
- Webhook server is unauthenticated if `WEBHOOK_SECRET` is empty — always set it
- PC control tools have no sandboxing — the agent has full desktop access
- Telegram bot only responds to `TELEGRAM_USER_ID` (or everyone if set to 0)
- Self-evolution requires human PR review by default (`SELF_EVOLVE_AUTO_MERGE=false`)
