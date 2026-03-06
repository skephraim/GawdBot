"""
Persistent memory — SQLite with two search modes:

1. Fast keyword search (LIKE) — zero cost, used for conversation context
2. Semantic embedding search — only used when explicitly saving/searching memory

CPU optimisation: embeddings are NOT generated for every conversation turn.
They are only generated when the agent explicitly calls save_memory() or search_memory().
Conversation history is retrieved by recency (SQL only, instant).
"""

from __future__ import annotations
import json
import sqlite3
from typing import Optional

import config
from core.llm import embed, cosine_similarity


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT    NOT NULL,
            category    TEXT    DEFAULT 'general',
            embedding   TEXT,
            source      TEXT    DEFAULT 'chat',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            interface   TEXT    DEFAULT 'chat',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_mem_category  ON memories(category);
    """)
    conn.commit()
    conn.close()


# ── Long-term memory (embedding-backed) ──────────────────────────────────────

async def save_memory(
    content: str,
    category: str = "general",
    source: str = "chat",
) -> int:
    """Save a fact/goal/note with an embedding for future semantic search."""
    embedding = await embed(content, input_type="passage")
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO memories (content, category, embedding, source) VALUES (?, ?, ?, ?)",
        (content, category, json.dumps(embedding), source),
    )
    conn.commit()
    mem_id = cur.lastrowid
    conn.close()
    return mem_id


async def search_memory(
    query: str,
    limit: Optional[int] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """Semantic search over saved memories. Generates one embedding for the query."""
    limit = limit or config.MEMORY_MAX_RESULTS
    q_emb = await embed(query, input_type="query")

    conn = _conn()
    sql = "SELECT id, content, category, source, created_at, embedding FROM memories"
    params: list = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    scored = []
    for row in rows:
        if not row["embedding"]:
            continue
        score = cosine_similarity(q_emb, json.loads(row["embedding"]))
        if score >= config.MEMORY_SCORE_THRESHOLD:
            scored.append({
                "id": row["id"],
                "content": row["content"],
                "category": row["category"],
                "source": row["source"],
                "created_at": row["created_at"],
                "score": score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def keyword_search_memory(query: str, limit: int = 3) -> list[dict]:
    """
    Fast keyword search — no embeddings, no LLM call.
    Used as a cheap fallback to inject context without slowing down every message.
    """
    conn = _conn()
    # Search for any word from the query (3+ chars) in memory content
    words = [w for w in query.split() if len(w) >= 3]
    if not words:
        conn.close()
        return []

    conditions = " OR ".join(["content LIKE ?" for _ in words])
    params = [f"%{w}%" for w in words]
    rows = conn.execute(
        f"SELECT content, category, created_at FROM memories WHERE {conditions} "
        f"ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Conversation history (no embeddings) ─────────────────────────────────────

def save_conversation(role: str, content: str, interface: str = "chat") -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO conversations (role, content, interface) VALUES (?, ?, ?)",
        (role, content, interface),
    )
    conn.commit()
    conn.close()


def get_recent_conversations(limit: Optional[int] = None) -> list[dict]:
    limit = limit or config.CONVERSATION_HISTORY_LIMIT
    conn = _conn()
    rows = conn.execute(
        "SELECT role, content, interface, created_at FROM conversations "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]
