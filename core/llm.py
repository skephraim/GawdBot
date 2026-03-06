"""
LLM client — OpenAI-compatible interface for NVIDIA NIM and Ollama.

CPU optimisations:
- OLLAMA_KEEP_ALIVE: keeps model loaded in RAM between calls (no reload cost)
- Dual model: fast CHAT_MODEL for conversation, AGENT_MODEL only for tool-heavy tasks
- stream_chat(): async generator for streaming responses to the UI
"""

from __future__ import annotations
import asyncio
from typing import Any, AsyncGenerator

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
                api_key="ollama",
                base_url=config.OLLAMA_BASE_URL,
            )
    return _client


def chat_model() -> str:
    return config.NVIDIA_CHAT_MODEL if config.LLM_BACKEND == "nvidia" else config.OLLAMA_CHAT_MODEL


def agent_model() -> str:
    """Stronger model — only used when tools are needed."""
    if config.LLM_BACKEND == "nvidia":
        return config.NVIDIA_CHAT_MODEL
    return config.OLLAMA_AGENT_MODEL


def embed_model() -> str:
    return config.NVIDIA_EMBED_MODEL if config.LLM_BACKEND == "nvidia" else config.OLLAMA_EMBED_MODEL


def _extra_body() -> dict:
    """Ollama-specific extras passed via extra_body."""
    if config.LLM_BACKEND == "ollama":
        return {"keep_alive": config.OLLAMA_KEEP_ALIVE}
    return {}


async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    use_agent_model: bool = False,
    **kwargs,
) -> Any:
    """Single-shot LLM call. Returns the response message object."""
    client = _get_client()
    model = agent_model() if (use_agent_model or tools) else chat_model()
    params: dict[str, Any] = dict(
        model=model,
        messages=messages,
        extra_body=_extra_body(),
        **kwargs,
    )
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    response = await client.chat.completions.create(**params)
    return response.choices[0].message


async def stream_chat(
    messages: list[dict],
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Stream a response token-by-token.
    Yields text chunks as they arrive — no tools, pure chat.
    Uses the fast CHAT_MODEL only.
    """
    client = _get_client()
    stream = await client.chat.completions.create(
        model=chat_model(),
        messages=messages,
        stream=True,
        extra_body=_extra_body(),
        **kwargs,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def embed(text: str, input_type: str = "passage") -> list[float]:
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
