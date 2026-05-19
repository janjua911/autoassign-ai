"""
core/database.py
SQLite database — tracks every assignment from detection to submission.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

DB_PATH = Path(__file__).parent.parent / "outputs" / "autoassign.db"


class Database:
    """
    Tracks assignments through their full lifecycle:
    detected → extracted → solved → approved → submitted
    """

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    subject     TEXT,
                    deadline    TEXT,
                    source      TEXT,
                    raw_text    TEXT,
                    questions   TEXT,
                    answers     TEXT,
                    status      TEXT DEFAULT 'detected',
                    confidence  INTEGER DEFAULT 0,
                    drive_link  TEXT,
                    pdf_path    TEXT,
                    docx_path   TEXT,
                    error_msg   TEXT,
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    updated_at  TEXT DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id   INTEGER,
                    event           TEXT NOT NULL,
                    detail          TEXT,
                    created_at      TEXT DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY(assignment_id) REFERENCES assignments(id)
                );
            """)
        logger.info(f"Database ready: {self.db_path}")

    def create_assignment(self, title: str, subject: str = "", deadline: str = "",
                          source: str = "teams", raw_text: str = "") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO assignments (title, subject, deadline, source, raw_text) VALUES (?, ?, ?, ?, ?)",
                (title, subject, deadline, source, raw_text)
            )
            assignment_id = cur.lastrowid
        self.log(assignment_id, "created", f"Source: {source}")
        logger.info(f"Assignment #{assignment_id} created: {title}")
        return assignment_id

    def update(self, assignment_id: int, **fields):
        if not fields:
            return
        for k, v in fields.items():
            if isinstance(v, (list, dict)):
                fields[k] = json.dumps(v, ensure_ascii=False)
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [assignment_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE assignments SET {set_clause} WHERE id = ?", values)

    def set_status(self, assignment_id: int, status: str, detail: str = ""):
        self.update(assignment_id, status=status)
        self.log(assignment_id, f"status:{status}", detail)
        logger.info(f"Assignment #{assignment_id} → {status}")

    def get(self, assignment_id: int) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        for field in ("questions", "answers"):
            if data.get(field):
                try:
                    data[field] = json.loads(data[field])
                except Exception:
                    pass
        return data

    def get_pending(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assignments WHERE status NOT IN ('submitted', 'error', 'skipped') ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all(self, limit: int = 50) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assignments ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def log(self, assignment_id: int, event: str, detail: str = ""):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO logs (assignment_id, event, detail) VALUES (?, ?, ?)",
                (assignment_id, event, detail or "")
            )

    def get_logs(self, assignment_id: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM logs WHERE assignment_id = ? ORDER BY created_at",
                (assignment_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]
            submitted = conn.execute(
                "SELECT COUNT(*) FROM assignments WHERE status='submitted'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM assignments WHERE status NOT IN ('submitted','error','skipped')"
            ).fetchone()[0]
        return {"total": total, "submitted": submitted, "pending": pending}


db = Database()
