"""
LLM client — single OpenAI-compatible interface for NVIDIA NIM and Ollama.
Switch backends via LLM_BACKEND env var without changing any other code.
"""

from __future__ import annotations
import asyncio
from typing import Any

import numpy as np
from openai import AsyncOpenAI

import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if config.LLM_BACKEND == "nvidia":
            _client = AsyncOpenAI(
                api_key=config.NVIDIA_API_KEY,
                base_url=config.NVIDIA_BASE_URL,
            )
        else:
            _client = AsyncOpenAI(
                api_key="ollama",  # Ollama ignores the key
                base_url=config.OLLAMA_BASE_URL,
            )
    return _client


def chat_model() -> str:
    return config.NVIDIA_CHAT_MODEL if config.LLM_BACKEND == "nvidia" else config.OLLAMA_CHAT_MODEL


def embed_model() -> str:
    return config.NVIDIA_EMBED_MODEL if config.LLM_BACKEND == "nvidia" else config.OLLAMA_EMBED_MODEL


async def chat(messages: list[dict], tools: list[dict] | None = None, **kwargs) -> Any:
    """Call LLM and return the response message object."""
    client = _get_client()
    params: dict[str, Any] = dict(model=chat_model(), messages=messages, **kwargs)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    response = await client.chat.completions.create(**params)
    return response.choices[0].message


async def embed(text: str, input_type: str = "passage") -> list[float]:
    """
    Generate an embedding for text.
    input_type: "passage" for storage, "query" for search — matters for NVIDIA NIM models.
    """
    client = _get_client()
    extra: dict[str, Any] = {}
    if config.LLM_BACKEND == "nvidia":
        extra["extra_body"] = {"input_type": input_type}
    response = await client.embeddings.create(
        model=embed_model(),
        input=text,
        **extra,
    )
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
