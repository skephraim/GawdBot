"""
Voice pipeline: wake word (openwakeword) → STT (faster-whisper) → TTS (piper).
Designed to run in a background thread alongside the async Telegram bot.
"""

from __future__ import annotations
import asyncio
import io
import threading
import wave
from typing import Callable, Optional

import numpy as np
import pyaudio

import config

_pa = pyaudio.PyAudio()

# ── Singletons (loaded once, shared across voice loop + Telegram) ─────────────
_whisper_model = None
_piper_voice = None
_whisper_lock = threading.Lock()
_piper_lock = threading.Lock()


def get_whisper():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            print(f"[Voice] Loading Whisper ({config.WHISPER_MODEL_SIZE})...")
            _whisper_model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device=config.WHISPER_DEVICE,
                compute_type="float16" if config.WHISPER_DEVICE == "cuda" else "int8",
            )
            print("[Voice] Whisper loaded.")
    return _whisper_model


def get_piper() -> Optional[object]:
    global _piper_voice
    with _piper_lock:
        if _piper_voice is None:
            from pathlib import Path
            voice_dir = Path.home() / ".local" / "share" / "piper"
            onnx = voice_dir / f"{config.TTS_VOICE_MODEL}.onnx"
            if not onnx.exists():
                print(
                    f"[Voice] TTS model not found at {onnx}.\n"
                    f"        Download from https://huggingface.co/rhasspy/piper-voices\n"
                    f"        Voice responses will be skipped."
                )
                return None
            from piper.voice import PiperVoice
            print(f"[Voice] Loading Piper TTS ({config.TTS_VOICE_MODEL})...")
            _piper_voice = PiperVoice.load(str(onnx))
            print("[Voice] Piper loaded.")
    return _piper_voice


# ── STT ───────────────────────────────────────────────────────────────────────

def transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV audio bytes to text using faster-whisper."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp = f.name
    try:
        segments, _ = get_whisper().transcribe(tmp, beam_size=5)
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        os.unlink(tmp)


# ── TTS ───────────────────────────────────────────────────────────────────────

def speak(text: str) -> None:
    """Synthesize text and play it through the default audio output."""
    piper = get_piper()
    if not piper or not text:
        return
    stream = _pa.open(format=pyaudio.paInt16, channels=1, rate=22050, output=True)
    try:
        for chunk in piper.synthesize_stream_raw(text):
            stream.write(chunk)
    finally:
        stream.stop_stream()
        stream.close()


# ── Recording ─────────────────────────────────────────────────────────────────

def _record_until_silence(silence_timeout: float = None) -> bytes:
    """Record from mic until silence, return WAV bytes."""
    silence_timeout = silence_timeout or config.SILENCE_TIMEOUT
    silence_limit = int(config.AUDIO_SAMPLE_RATE * silence_timeout / config.AUDIO_CHUNK_SIZE)
    frames = []
    silence_frames = 0

    stream = _pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=config.AUDIO_SAMPLE_RATE,
        input=True,
        frames_per_buffer=config.AUDIO_CHUNK_SIZE,
    )
    try:
        while True:
            data = stream.read(config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            energy = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float32) ** 2))
            if energy < 500:
                silence_frames += 1
                if silence_frames >= silence_limit:
                    break
            else:
                silence_frames = 0
    finally:
        stream.stop_stream()
        stream.close()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(config.AUDIO_SAMPLE_RATE)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


# ── Wake Word Loop ────────────────────────────────────────────────────────────

def run_voice_loop(on_speech: Callable[[str], str], main_loop: asyncio.AbstractEventLoop) -> None:
    """
    Blocking wake-word loop. Run this in a daemon thread.

    on_speech is an async coroutine — it's scheduled on main_loop via
    run_coroutine_threadsafe so it shares the same event loop as Telegram.
    """
    from openwakeword.model import Model

    # Pre-load models in the voice thread
    get_whisper()
    get_piper()

    print(f"[Voice] Loading wake word model: {config.WAKE_WORD_MODEL}")
    ww = Model(wakeword_models=[config.WAKE_WORD_MODEL], inference_framework="onnx")

    stream = _pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=config.AUDIO_SAMPLE_RATE,
        input=True,
        frames_per_buffer=config.AUDIO_CHUNK_SIZE,
    )

    print(f"[Voice] Listening for '{config.WAKE_WORD_MODEL}'...")

    try:
        while True:
            chunk = stream.read(config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            samples = np.frombuffer(chunk, dtype=np.int16)
            ww.predict(samples)

            score = ww.prediction_buffer[config.WAKE_WORD_MODEL][-1]
            if score < config.WAKE_WORD_THRESHOLD:
                continue

            print("[Voice] Wake word detected — listening...")
            wav = _record_until_silence()
            text = transcribe(wav)

            if not text:
                continue

            print(f"[Voice] Heard: {text}")
            future = asyncio.run_coroutine_threadsafe(on_speech(text), main_loop)
            try:
                response = future.result(timeout=60)
                print(f"[Voice] Responding: {response}")
                speak(response)
            except Exception as e:
                print(f"[Voice] Agent error: {e}")
    finally:
        stream.stop_stream()
        stream.close()
