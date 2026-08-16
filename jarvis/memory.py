from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import settings


class MemoryStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_messages_session
                            ON messages(session_id, id)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def new_session(self, title: str = 'New chat') -> str:
        session_id = uuid4().hex[:12]
        with self._lock, self._connect() as conn:
            conn.execute('INSERT INTO sessions(id, title, created_at) VALUES (?, ?, ?)',
                         (session_id, title[:100], self._now()))
            conn.commit()
        return session_id

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)',
                (session_id, role, content, self._now()),
            )
            conn.commit()

    def recent_messages(self, session_id: str, limit: int | None = None) -> list[tuple[str, str]]:
        limit = limit or settings.history_messages
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?',
                (session_id, limit),
            ).fetchall()
        return [(r['role'], r['content']) for r in reversed(rows)]

    def remember(self, fact: str) -> str:
        fact = fact.strip()
        if not fact:
            return 'Nothing to remember.'
        if len(fact) > 2000:
            fact = fact[:2000]
        with self._lock, self._connect() as conn:
            conn.execute('INSERT INTO facts(fact, created_at) VALUES (?, ?)', (fact, self._now()))
            conn.commit()
        return 'Remembered.'

    def recall(self, query: str, limit: int = 8) -> list[str]:
        q = f'%{query.strip()}%'
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT fact FROM facts WHERE fact LIKE ? ORDER BY id DESC LIMIT ?',
                (q, max(1, min(limit, 20))),
            ).fetchall()
        return [r['fact'] for r in rows]

    def recent_facts(self, limit: int = 10) -> list[str]:
        with self._lock, self._connect() as conn:
            rows = conn.execute('SELECT fact FROM facts ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [r['fact'] for r in rows]

    def list_sessions(self, limit: int = 12) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT id, title, created_at FROM sessions ORDER BY created_at DESC LIMIT ?',
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
