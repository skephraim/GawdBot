"""
GawdBot core agent — agentic loop with tool calling.
Receives messages from any interface (voice, Telegram) and returns responses.
"""

from __future__ import annotations
import json
from typing import Optional

import config
from core import llm, memory
from tools import git_tools, code_tools, pc_control

SYSTEM_PROMPT = """You are GawdBot — a self-evolving AI assistant. You are capable, direct, and helpful.

You have tools for:
- Reading and writing files (including your own source code)
- Running shell commands
- Git operations: commit, branch, push, create PRs
- Persistent semantic memory: search past conversations, save important facts
- Self-improvement: modify your own code via git branches

When asked to improve yourself, read CLAUDE.md first for architecture context, then make targeted changes,
commit to a branch, and notify the user for review (unless auto-merge is configured).

Be concise. Prefer action over explanation. Ask one focused question if you're uncertain.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (relative to project root or absolute)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates or overwrites)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and return its output",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get current git status",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Get git diff (optionally for a specific file)",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Specific file to diff (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Get recent git commit history",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Number of commits to show (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage files and create a git commit",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to stage. Use ['.'] for all changes.",
                    },
                },
                "required": ["message", "files"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_create_branch",
            "description": "Create and checkout a new git branch",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push the current branch to remote origin",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Branch name (optional, defaults to current)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_github_pr",
            "description": "Create a GitHub pull request",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "head": {"type": "string", "description": "Source branch"},
                    "base": {"type": "string", "description": "Target branch (usually 'main')"},
                },
                "required": ["title", "body", "head", "base"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search persistent memory for relevant context",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "Filter by category: fact | goal | code | general (optional)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save important information to persistent memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "Category: fact | goal | code | general",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_project_files",
            "description": "List all source files in the GawdBot project (useful for self-improvement)",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ── PC Control ───────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Click the mouse at screen coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "description": "left | right | middle (default: left)"},
                    "clicks": {"type": "integer", "description": "Number of clicks (default: 1)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_move",
            "description": "Move the mouse cursor to screen coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text using the keyboard",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a key or hotkey combo (e.g. 'enter', 'ctrl+c', 'alt+F4')",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot and return it as base64 PNG",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[x, y, width, height] — omit for full screen",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clipboard",
            "description": "Read the current clipboard contents",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_clipboard",
            "description": "Set the clipboard to a given text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "List all open windows",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Bring a window to the foreground by title substring",
            "parameters": {
                "type": "object",
                "properties": {"title_substr": {"type": "string"}},
                "required": ["title_substr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Launch an application by command name (e.g. 'firefox', 'code', 'nautilus')",
            "parameters": {
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_size",
            "description": "Get the screen dimensions",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mouse_position",
            "description": "Get the current mouse cursor position",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ── Embeddings ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "generate_embedding",
            "description": "Generate a text embedding vector for one or more texts",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "input_type": {"type": "string", "description": "passage or query"},
                },
                "required": ["text"],
            },
        },
    },
    # ── Phone control (Android) ───────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "phone_screenshot",
            "description": "Take a screenshot of the connected Android phone screen. Returns base64 PNG.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_phone_screen",
            "description": "Take a screenshot and analyze it with the vision LLM to understand what's on the phone screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What to look for or ask about the screen. Default: describe all UI elements and their positions.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_tap",
            "description": "Tap at a specific coordinate on the phone screen",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate in pixels"},
                    "y": {"type": "integer", "description": "Y coordinate in pixels"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_swipe",
            "description": "Swipe on the phone screen",
            "parameters": {
                "type": "object",
                "properties": {
                    "startX": {"type": "integer"},
                    "startY": {"type": "integer"},
                    "endX": {"type": "integer"},
                    "endY": {"type": "integer"},
                    "duration_ms": {"type": "integer", "description": "Swipe duration in ms (default 300)"},
                },
                "required": ["startX", "startY", "endX", "endY"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_type",
            "description": "Type text into the currently focused input on the phone",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_key",
            "description": "Press a system key on the phone",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key name: BACK | HOME | RECENTS | NOTIFICATIONS | VOLUME_UP | VOLUME_DOWN | POWER | ENTER",
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_open_url",
            "description": "Open a URL in the phone browser",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_web_search",
            "description": "Perform a web search on the phone using the built-in browser",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "phone_status",
            "description": "Check if a phone is connected and get its screen dimensions",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def _execute_tool(name: str, args: dict, interface: str = "chat") -> str:
    try:
        if name == "read_file":
            return code_tools.read_file(args["path"])
        elif name == "write_file":
            return code_tools.write_file(args["path"], args["content"])
        elif name == "run_command":
            return await code_tools.run_command(args["command"], args.get("cwd"))
        elif name == "git_status":
            return git_tools.status()
        elif name == "git_diff":
            return git_tools.diff(args.get("file"))
        elif name == "git_log":
            return git_tools.log(args.get("n", 10))
        elif name == "git_commit":
            return git_tools.commit(args["message"], args["files"])
        elif name == "git_create_branch":
            return git_tools.create_branch(args["name"])
        elif name == "git_push":
            return git_tools.push(args.get("branch"))
        elif name == "create_github_pr":
            return await git_tools.create_pr(args["title"], args["body"], args["head"], args["base"])
        elif name == "search_memory":
            results = await memory.search_memory(args["query"], category=args.get("category"))
            if not results:
                return "No relevant memories found."
            return "\n".join(f"[{r['category']}] {r['content']}" for r in results)
        elif name == "save_memory":
            await memory.save_memory(args["content"], category=args.get("category", "general"), source=interface)
            return "Memory saved."
        elif name == "list_project_files":
            return code_tools.list_project_files()
        # ── PC Control ────────────────────────────────────────────────────────
        elif name == "mouse_click":
            return pc_control.mouse_click(args["x"], args["y"], args.get("button", "left"), args.get("clicks", 1))
        elif name == "mouse_move":
            return pc_control.mouse_move(args["x"], args["y"])
        elif name == "type_text":
            return pc_control.type_text(args["text"])
        elif name == "press_key":
            return pc_control.press_key(args["key"])
        elif name == "take_screenshot":
            region = args.get("region")
            return pc_control.take_screenshot(tuple(region) if region else None)
        elif name == "get_clipboard":
            return pc_control.get_clipboard()
        elif name == "set_clipboard":
            return pc_control.set_clipboard(args["text"])
        elif name == "list_windows":
            return pc_control.list_windows()
        elif name == "focus_window":
            return pc_control.focus_window(args["title_substr"])
        elif name == "open_app":
            return pc_control.open_app(args["app"])
        elif name == "get_screen_size":
            return pc_control.get_screen_size()
        elif name == "get_mouse_position":
            return pc_control.get_mouse_position()
        # ── Embeddings ────────────────────────────────────────────────────────
        elif name == "generate_embedding":
            embedding = await llm.embed(args["text"], input_type=args.get("input_type", "passage"))
            return json.dumps({"embedding": embedding, "dimensions": len(embedding)})
        # ── Phone control ─────────────────────────────────────────────────────
        elif name == "phone_status":
            from interfaces.webhook_server import get_connected_phone, _phone_meta
            conn = get_connected_phone()
            if not conn:
                return "No phone connected. Open the GawdBot Android app and connect."
            device_id, _ = conn
            meta = _phone_meta.get(device_id, {})
            return f"Phone connected: {meta.get('name', 'Unknown')} — screen {meta.get('width')}×{meta.get('height')}px"
        elif name == "phone_screenshot":
            from interfaces.webhook_server import get_phone_screenshot
            img = await get_phone_screenshot()
            if img is None:
                return "No phone connected or screenshot timed out."
            return img  # base64 PNG — can be passed to analyze_phone_screen
        elif name == "analyze_phone_screen":
            from interfaces.webhook_server import get_phone_screenshot, _phone_meta, get_connected_phone
            from tools.vision import analyze_image
            img = await get_phone_screenshot()
            if img is None:
                return "No phone connected or screenshot timed out."
            conn = get_connected_phone()
            meta = _phone_meta.get(conn[0], {}) if conn else {}
            question = args.get("question", "Describe all visible UI elements and their pixel positions so I can interact with them.")
            return await analyze_image(img, question, meta.get("width"), meta.get("height"))
        elif name == "phone_tap":
            from interfaces.webhook_server import send_phone_action
            ok = await send_phone_action("tap", {"x": args["x"], "y": args["y"]})
            return "Tapped." if ok else "Tap failed — no phone connected."
        elif name == "phone_swipe":
            from interfaces.webhook_server import send_phone_action
            ok = await send_phone_action("swipe", {
                "startX": args["startX"], "startY": args["startY"],
                "endX": args["endX"], "endY": args["endY"],
                "duration_ms": args.get("duration_ms", 300),
            })
            return "Swipe executed." if ok else "Swipe failed — no phone connected."
        elif name == "phone_type":
            from interfaces.webhook_server import send_phone_action
            ok = await send_phone_action("type", {"text": args["text"]})
            return "Text typed." if ok else "Type failed — no phone connected."
        elif name == "phone_key":
            from interfaces.webhook_server import send_phone_action
            ok = await send_phone_action("key", {"key": args["key"]})
            return f"Key {args['key']} pressed." if ok else "Key press failed — no phone connected."
        elif name == "phone_open_url":
            from interfaces.webhook_server import send_phone_action
            ok = await send_phone_action("open_url", {"url": args["url"]})
            return f"Opening {args['url']}." if ok else "Failed — no phone connected."
        elif name == "phone_web_search":
            from interfaces.webhook_server import send_phone_action
            import urllib.parse
            url = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(args['query'])}"
            ok = await send_phone_action("open_url", {"url": url})
            return f"Searching for '{args['query']}'." if ok else "Search failed — no phone connected."
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"


async def chat(user_message: str, interface: str = "chat") -> str:
    """Process a user message through the agentic loop and return a response."""
    memory.save_conversation("user", user_message, interface)

    # Inject relevant long-term memory as context
    relevant = await memory.search_memory(user_message)
    memory_context = ""
    if relevant:
        memory_context = "\n\nRelevant memory:\n" + "\n".join(
            f"- [{r['category']}] {r['content']}" for r in relevant
        )

    history = memory.get_recent_conversations()
    messages = [{"role": "system", "content": SYSTEM_PROMPT + memory_context}]
    # Include history but skip the message we just saved (last item)
    for h in history[:-1]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    # Agentic loop
    for _ in range(15):
        msg = await llm.chat(messages, tools=TOOLS)

        if not msg.tool_calls:
            response = msg.content or ""
            memory.save_conversation("assistant", response, interface)
            return response

        messages.append(msg)

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = await _execute_tool(tc.function.name, args, interface)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "Reached the action limit. Please try breaking your request into smaller steps."
