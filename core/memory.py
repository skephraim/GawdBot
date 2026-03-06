"""
Persistent memory — SQLite with embedding-based semantic search.
No external vector DB required.
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
    """)
    conn.commit()
    conn.close()


async def save_memory(
    content: str,
    category: str = "general",
    source: str = "chat",
) -> int:
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
