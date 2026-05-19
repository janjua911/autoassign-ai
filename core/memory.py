"""
core/memory.py
Simple key-value memory store for agents — persists to SQLite.
Used to share context between agents without re-fetching.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from loguru import logger

MEMORY_DB = Path(__file__).parent.parent / "outputs" / "memory.db"


class Memory:
    """
    Shared memory bus for all agents.
    Usage:
        from core.memory import memory
        memory.set("last_assignment_id", 5)
        val = memory.get("last_assignment_id")
    """

    def __init__(self):
        MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict = {}
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(MEMORY_DB)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    key         TEXT PRIMARY KEY,
                    value       TEXT,
                    updated_at  TEXT
                )
            """)

    def set(self, key: str, value) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        self._cache[key] = value
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)",
                (key, serialized, datetime.now().isoformat())
            )
        logger.debug(f"Memory set: {key}")

    def get(self, key: str, default=None):
        if key in self._cache:
            return self._cache[key]
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
        if row:
            val = json.loads(row["value"])
            self._cache[key] = val
            return val
        return default

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        with self._connect() as conn:
            conn.execute("DELETE FROM memory WHERE key = ?", (key,))

    def clear(self) -> None:
        self._cache.clear()
        with self._connect() as conn:
            conn.execute("DELETE FROM memory")
        logger.info("Memory cleared")

    def all(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM memory").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}


memory = Memory()
