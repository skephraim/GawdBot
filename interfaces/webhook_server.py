"""
GawdBot server interfaces:
  HTTP:      POST /webhook          — trigger agent
             POST /webhook/embed    — generate embeddings
             GET  /health           — liveness
  WebSocket: GET  /ws               — Android phone connection (control + screenshots)
"""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Optional

import aiohttp
from aiohttp import web

import config
from core.agent import chat as agent_chat
from core.llm import embed as llm_embed

logger = logging.getLogger("webhook")

routes = web.RouteTableDef()

# ── Phone client registry ─────────────────────────────────────────────────────
# Only one phone at a time for now; keyed by device_id
_phone_clients: dict[str, web.WebSocketResponse] = {}
_phone_meta: dict[str, dict] = {}  # device_id -> {name, width, height}

# Pending futures for async request/response with the phone
_screenshot_futures: dict[str, asyncio.Future] = {}  # request_id -> Future[str]
_action_futures: dict[str, asyncio.Future] = {}       # action_id  -> Future[bool]


def get_connected_phone() -> Optional[tuple[str, web.WebSocketResponse]]:
    """Return (device_id, ws) of the first connected phone, or None."""
    for device_id, ws in _phone_clients.items():
        if not ws.closed:
            return device_id, ws
    return None


async def get_phone_screenshot(timeout: float = 15.0) -> Optional[str]:
    """
    Request a screenshot from the connected phone.
    Returns base64-encoded PNG string, or None if no phone / timeout.
    """
    conn = get_connected_phone()
    if not conn:
        return None
    device_id, ws = conn
    request_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _screenshot_futures[request_id] = future
    try:
        await ws.send_str(json.dumps({"type": "request_screenshot", "request_id": request_id}))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        _screenshot_futures.pop(request_id, None)


async def send_phone_action(action: str, params: dict, timeout: float = 10.0) -> bool:
    """
    Send a control action to the connected phone and wait for confirmation.
    action: "tap" | "swipe" | "type" | "key" | "open_url"
    """
    conn = get_connected_phone()
    if not conn:
        return False
    device_id, ws = conn
    action_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _action_futures[action_id] = future
    try:
        msg = {"type": "action", "action_id": action_id, "action": action, **params}
        await ws.send_str(json.dumps(msg))
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return False
    finally:
        _action_futures.pop(action_id, None)


async def notify_phone(title: str, body: str) -> bool:
    """Push a notification to the connected phone."""
    conn = get_connected_phone()
    if not conn:
        return False
    _, ws = conn
    await ws.send_str(json.dumps({"type": "notification", "title": title, "body": body}))
    return True


# ── WebSocket handler ─────────────────────────────────────────────────────────

@routes.get("/ws")
async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    device_id: Optional[str] = None

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "hello":
                device_id = data.get("device_id", str(uuid.uuid4()))
                _phone_clients[device_id] = ws
                _phone_meta[device_id] = {
                    "name": data.get("device_name", "Unknown"),
                    "width": data.get("screen_width", 1080),
                    "height": data.get("screen_height", 1920),
                }
                logger.info(f"Phone connected: {_phone_meta[device_id]['name']} ({device_id})")
                await ws.send_str(json.dumps({"type": "welcome", "status": "connected"}))

            elif msg_type == "screenshot_response":
                request_id = data.get("request_id")
                if request_id and request_id in _screenshot_futures:
                    fut = _screenshot_futures[request_id]
                    if not fut.done():
                        fut.set_result(data.get("image"))

            elif msg_type == "action_done":
                action_id = data.get("action_id")
                if action_id and action_id in _action_futures:
                    fut = _action_futures[action_id]
                    if not fut.done():
                        fut.set_result(data.get("success", True))

            elif msg_type == "user_message":
                text = data.get("text", "").strip()
                if text:
                    response = await agent_chat(text, interface="android")
                    await ws.send_str(json.dumps({"type": "response", "text": response}))

            elif msg_type == "ping":
                await ws.send_str(json.dumps({"type": "pong"}))

        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
            break

    if device_id:
        _phone_clients.pop(device_id, None)
        _phone_meta.pop(device_id, None)
        logger.info(f"Phone disconnected: {device_id}")

    return ws


# ── HTTP endpoints ────────────────────────────────────────────────────────────

def _authorized(request: web.Request) -> bool:
    if not config.WEBHOOK_SECRET:
        return True
    secret = (
        request.headers.get("X-Webhook-Secret")
        or request.rel_url.query.get("secret", "")
    )
    import hmac
    return hmac.compare_digest(secret, config.WEBHOOK_SECRET)


@routes.get("/health")
async def health(request: web.Request) -> web.Response:
    phone = get_connected_phone()
    phone_info = None
    if phone:
        device_id, _ = phone
        phone_info = _phone_meta.get(device_id)
    return web.json_response({
        "status": "ok",
        "bot": "GawdBot",
        "phone_connected": phone_info is not None,
        "phone": phone_info,
    })


@routes.post("/webhook")
async def webhook(request: web.Request) -> web.Response:
    if not _authorized(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    message = body.get("message", "").strip()
    if not message:
        return web.json_response({"error": "message field required"}, status=400)
    try:
        response = await agent_chat(message, interface=body.get("interface", "webhook"))
        return web.json_response({"response": response})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@routes.post("/webhook/embed")
async def embed_endpoint(request: web.Request) -> web.Response:
    if not _authorized(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    input_type = body.get("input_type", "passage")
    texts = [body["text"]] if "text" in body else body.get("texts", [])
    if not texts:
        return web.json_response({"error": "text or texts field required"}, status=400)
    try:
        embeddings = [await llm_embed(t, input_type=input_type) for t in texts]
        result = embeddings[0] if len(embeddings) == 1 else embeddings
        return web.json_response({"embedding": result})
    except Exception as e:
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
    print(f"[Server] HTTP  → http://{host}:{port}/webhook")
    print(f"[Server] WS    → ws://{host}:{port}/ws")
    print(f"[Server] Health→ http://{host}:{port}/health")
    if not config.WEBHOOK_SECRET:
        print("[Server] WARNING: WEBHOOK_SECRET not set — endpoints unauthenticated!")
