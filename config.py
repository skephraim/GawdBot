import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── LLM Backend ───────────────────────────────────────────────────────────────
# "nvidia" → NVIDIA NIM (cloud, OpenAI-compatible)
# "ollama" → local Ollama (OpenAI-compatible)
LLM_BACKEND = os.getenv("LLM_BACKEND", "nvidia")

# NVIDIA NIM
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_CHAT_MODEL = os.getenv("NVIDIA_CHAT_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_EMBED_MODEL = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", "nvidia/llama-3.2-11b-vision-instruct")

# Ollama (local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
# CHAT_MODEL: fast model for everyday conversation (llama3.2:1b is snappy on CPU)
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
# AGENT_MODEL: stronger model only for coding / self-evolution tasks
OLLAMA_AGENT_MODEL = os.getenv("OLLAMA_AGENT_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "moondream")  # 1.7GB, fast on CPU
# Keep models loaded in RAM between calls (0 = unload immediately, -1 = keep forever)
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID") or "0")

# ── Voice ─────────────────────────────────────────────────────────────────────
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"
WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")   # tiny=fastest on CPU
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
TTS_VOICE_MODEL = os.getenv("TTS_VOICE_MODEL", "en_GB-northern_english_male-medium")
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = 1280  # 80ms at 16kHz — openwakeword requirement
SILENCE_TIMEOUT = float(os.getenv("SILENCE_TIMEOUT", "2.0"))

# ── GitHub (coding agent + self-evolution) ────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # "owner/repo"

# ── Memory ────────────────────────────────────────────────────────────────────
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "data/memory.db")
MEMORY_MAX_RESULTS = int(os.getenv("MEMORY_MAX_RESULTS", "5"))
MEMORY_SCORE_THRESHOLD = float(os.getenv("MEMORY_SCORE_THRESHOLD", "0.6"))
CONVERSATION_HISTORY_LIMIT = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "20"))

# ── Self-Evolution ────────────────────────────────────────────────────────────
SELF_EVOLVE_ENABLED = os.getenv("SELF_EVOLVE_ENABLED", "true").lower() == "true"
SELF_EVOLVE_AUTO_MERGE = os.getenv("SELF_EVOLVE_AUTO_MERGE", "false").lower() == "true"
SELF_EVOLVE_BRANCH_PREFIX = "nexus/evolve"

# ── Webhook server ────────────────────────────────────────────────────────────
WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "true").lower() == "true"
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # Set this — unauthenticated if empty

# ── Project ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
