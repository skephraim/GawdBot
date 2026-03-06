"""
Webhook server — receive external HTTP triggers and route them through GawdBot.

Endpoints:
  POST /webhook          — trigger agent with a message payload
  POST /webhook/embed    — generate embeddings for text
  GET  /health           — liveness check

Authentication: shared secret via X-Webhook-Secret header or `secret` query param.
"""

from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging

from aiohttp import web

import config
from core.agent import chat as agent_chat
from core.llm import embed as llm_embed

logger = logging.getLogger("webhook")

routes = web.RouteTableDef()


def _authorized(request: web.Request) -> bool:
    if not config.WEBHOOK_SECRET:
        return True  # No secret configured — open (add to .env!)
    secret = (
        request.headers.get("X-Webhook-Secret")
        or request.rel_url.query.get("secret", "")
    )
    return hmac.compare_digest(secret, config.WEBHOOK_SECRET)


@routes.get("/health")
async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "bot": "GawdBot"})


@routes.post("/webhook")
async def webhook(request: web.Request) -> web.Response:
    """
    Trigger GawdBot with a message.

    Body (JSON):
      { "message": "do something", "interface": "webhook" }
    """
    if not _authorized(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    message = body.get("message", "").strip()
    if not message:
        return web.json_response({"error": "message field required"}, status=400)

    interface = body.get("interface", "webhook")

    try:
        response = await agent_chat(message, interface=interface)
        return web.json_response({"response": response})
    except Exception as e:
        logger.error(f"Webhook agent error: {e}")
        return web.json_response({"error": str(e)}, status=500)


@routes.post("/webhook/embed")
async def embed_endpoint(request: web.Request) -> web.Response:
    """
    Generate embeddings for one or more texts.

    Body (JSON):
      { "text": "single string" }
      or
      { "texts": ["string1", "string2"], "input_type": "passage" }
    """
    if not _authorized(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    input_type = body.get("input_type", "passage")

    if "text" in body:
        texts = [body["text"]]
    elif "texts" in body:
        texts = body["texts"]
    else:
        return web.json_response({"error": "text or texts field required"}, status=400)

    try:
        embeddings = []
        for t in texts:
            emb = await llm_embed(t, input_type=input_type)
            embeddings.append(emb)
        result = embeddings[0] if len(embeddings) == 1 else embeddings
        return web.json_response({"embedding": result, "model": config.NVIDIA_EMBED_MODEL if config.LLM_BACKEND == "nvidia" else config.OLLAMA_EMBED_MODEL})
    except Exception as e:
        logger.error(f"Embed error: {e}")
        return web.json_response({"error": str(e)}, status=500)


def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app


async def run(host: str = "0.0.0.0", port: int = None) -> None:
    port = port or config.WEBHOOK_PORT
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"[Webhook] Server running on http://{host}:{port}")
    print(f"[Webhook] Endpoints: POST /webhook  POST /webhook/embed  GET /health")
    if not config.WEBHOOK_SECRET:
        print("[Webhook] WARNING: WEBHOOK_SECRET not set — server is unauthenticated!")
