from __future__ import annotations

import re
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
            conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL UNIQUE,
                added_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY(doc_id) REFERENCES knowledge_docs(id)
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_knowledge_doc
                            ON knowledge_chunks(doc_id, chunk_index)''')
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

    def session_messages(self, session_id: str, limit: int = 500) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id ASC LIMIT ?',
                (session_id, max(1, min(limit, 2000))),
            ).fetchall()
        return [dict(r) for r in rows]

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

    def stats(self) -> dict:
        with self._lock, self._connect() as conn:
            sessions = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
            messages = conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]
            facts = conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0]
            docs = conn.execute('SELECT COUNT(*) FROM knowledge_docs').fetchone()[0]
            chunks = conn.execute('SELECT COUNT(*) FROM knowledge_chunks').fetchone()[0]
        return {
            'sessions': sessions,
            'messages': messages,
            'facts': facts,
            'knowledge_docs': docs,
            'knowledge_chunks': chunks,
        }

    def export_session(self, session_id: str, export_dir: Path) -> Path:
        export_dir.mkdir(parents=True, exist_ok=True)
        messages = self.session_messages(session_id, 2000)
        target = export_dir / f'jarvis-chat-{session_id}.md'
        lines = [f'# JARVIS OMEGA Chat Export', '', f'Session: `{session_id}`', '']
        for row in messages:
            who = 'YOU' if row['role'] == 'user' else 'JARVIS'
            lines.extend([f'## {who}', '', row['content'], ''])
        target.write_text('\n'.join(lines), encoding='utf-8')
        return target

    @staticmethod
    def _chunks(text: str, size: int = 1800, overlap: int = 180) -> list[str]:
        clean = re.sub(r'\s+', ' ', text).strip()
        if not clean:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + size)
            chunks.append(clean[start:end])
            if end >= len(clean):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def index_knowledge(self, source: str, text: str) -> dict:
        source = source.strip()[:1000]
        chunks = self._chunks(text)
        if not source or not chunks:
            return {'source': source, 'chunks': 0}
        with self._lock, self._connect() as conn:
            old = conn.execute('SELECT id FROM knowledge_docs WHERE source=?', (source,)).fetchone()
            if old:
                conn.execute('DELETE FROM knowledge_chunks WHERE doc_id=?', (old['id'],))
                conn.execute('UPDATE knowledge_docs SET added_at=? WHERE id=?', (self._now(), old['id']))
                doc_id = old['id']
            else:
                cur = conn.execute('INSERT INTO knowledge_docs(source, added_at) VALUES (?, ?)',
                                   (source, self._now()))
                doc_id = cur.lastrowid
            conn.executemany(
                'INSERT INTO knowledge_chunks(doc_id, chunk_index, content) VALUES (?, ?, ?)',
                [(doc_id, i, chunk) for i, chunk in enumerate(chunks)],
            )
            conn.commit()
        return {'source': source, 'chunks': len(chunks)}

    def search_knowledge(self, query: str, limit: int = 6) -> list[dict]:
        terms = [t.lower() for t in re.findall(r'[\w-]{2,}', query, flags=re.UNICODE)][:12]
        if not terms:
            return []
        with self._lock, self._connect() as conn:
            rows = conn.execute('''
                SELECT kd.source, kc.chunk_index, kc.content
                FROM knowledge_chunks kc
                JOIN knowledge_docs kd ON kd.id = kc.doc_id
                ORDER BY kc.id DESC
                LIMIT 2000
            ''').fetchall()
        scored = []
        for row in rows:
            lowered = row['content'].lower()
            score = sum(lowered.count(term) for term in terms)
            if score:
                scored.append((score, dict(row)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] | {'score': item[0]} for item in scored[:max(1, min(limit, 12))]]
