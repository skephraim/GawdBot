# GawdBot

A self-evolving AI assistant with voice control, Telegram, webhooks, and full PC access.

```
Voice (wake word) ─┐
Telegram           ├──► GawdBot Agent ──► Memory (SQLite + embeddings)
Webhooks (HTTP)    ┘         │
                             ├──► Files / Git / GitHub PRs
                             ├──► PC control (mouse, keyboard, windows)
                             └──► Self-improvement (reads + edits own code)
```

## Features

| Feature | How |
|---|---|
| Voice wake word | openwakeword (built-in "hey_jarvis") |
| Speech-to-text | faster-whisper on NVIDIA GPU |
| Text-to-speech | Piper TTS (local, offline) |
| Chat | Telegram bot + local voice |
| LLM backend | NVIDIA NIM (cloud) or Ollama (local) — same API, swap via env |
| Text embeddings | NVIDIA NIM or Ollama, exposed via `/webhook/embed` |
| Persistent memory | SQLite + cosine similarity search — no vector DB needed |
| Coding agent | Read/write files, run commands, git commit, create GitHub PRs |
| PC control | Mouse, keyboard, hotkeys, windows, clipboard, screenshots |
| Webhooks | POST `/webhook` to trigger agent; POST `/webhook/embed` for embeddings |
| Self-evolution | `/evolve <request>` → agent edits own code → git branch → PR |

## Quick Start

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# ffmpeg (for voice message transcoding in Telegram)
sudo apt install ffmpeg wmctrl xclip

# NVIDIA drivers + CUDA (for GPU voice processing)
nvidia-smi
```

### 2. Install

```bash
cd gawdbot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> On CPU-only machines, replace `onnxruntime-gpu` with `onnxruntime` in requirements.txt and set `WHISPER_DEVICE=cpu`.

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

Minimum required:
- `NVIDIA_API_KEY` or `LLM_BACKEND=ollama` with Ollama running
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_USER_ID`

### 4. TTS voice model (optional, for local voice output)

```bash
mkdir -p ~/.local/share/piper
# Download model from https://huggingface.co/rhasspy/piper-voices
# Example:
wget -P ~/.local/share/piper/ \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium.onnx.json
```

### 5. Run

```bash
python main.py
```

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Greeting |
| `/help` | Show commands |
| `/evolve <request>` | Trigger self-improvement cycle |
| `/memory <query>` | Search persistent memory |
| Any message | Chat with GawdBot |
| Voice message | Transcribed and handled as text |

## Webhook API

```bash
# Health check
curl http://localhost:8080/health

# Trigger agent
curl -X POST http://localhost:8080/webhook \
  -H "X-Webhook-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{"message": "what files are in the project?"}'

# Generate embeddings
curl -X POST http://localhost:8080/webhook/embed \
  -H "X-Webhook-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world", "input_type": "passage"}'

# Batch embeddings
curl -X POST http://localhost:8080/webhook/embed \
  -H "X-Webhook-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["first text", "second text"]}'
```

## Self-Evolution

GawdBot can modify its own code:

```
# Via Telegram
/evolve add a web search tool that uses DuckDuckGo

# Via voice
"Hey Jarvis, improve yourself — add rate limiting to the webhook server"
```

The agent reads `CLAUDE.md` for architecture context, edits source files, runs syntax checks, commits to a branch, and either:
- Creates a GitHub PR for review (`SELF_EVOLVE_AUTO_MERGE=false`, default)
- Auto-merges to main (`SELF_EVOLVE_AUTO_MERGE=true`, use carefully)

## LLM Backends

| Backend | Config | Notes |
|---|---|---|
| NVIDIA NIM | `LLM_BACKEND=nvidia` | Cloud, free tier at build.nvidia.com |
| Ollama | `LLM_BACKEND=ollama` | Fully local, runs on your GPU |

Both use identical OpenAI-compatible API — swap backends by changing one env var.

## PC Control

GawdBot has full desktop access via pyautogui:

- Mouse: move, click, scroll
- Keyboard: type text, press hotkeys (`ctrl+c`, `alt+F4`, etc.)
- Windows: list open windows, focus by title
- Clipboard: read and write
- Screenshots: full screen or region (returned as base64 PNG)
- Launch applications

**Example voice commands:**
- "Take a screenshot and tell me what's on screen"
- "Open Firefox"
- "Copy the clipboard contents"
- "Press Ctrl+Z"
