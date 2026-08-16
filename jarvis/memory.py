from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import settings
from .storage.sqlite_utils import connect_sqlite
from .vector_memory import rank_texts


class MemoryStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, timeout=10)

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
            conn.execute('''CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
            conn.execute('''CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                completed_at TEXT
            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                due_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                notified_at TEXT
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_reminders_due
                            ON reminders(status, due_at)''')
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

    def message_count(self, session_id: str) -> int:
        with self._lock, self._connect() as conn:
            return int(conn.execute('SELECT COUNT(*) FROM messages WHERE session_id=?', (session_id,)).fetchone()[0])

    def search_messages(self, query: str, limit: int = 20) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT session_id, role, content, created_at FROM messages
                   WHERE content LIKE ? ORDER BY id DESC LIMIT ?''',
                (f'%{query}%', max(1, min(limit, 50))),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_session_summary(self, session_id: str, summary: str) -> None:
        summary = summary.strip()[:12000]
        if not summary:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                '''INSERT INTO session_summaries(session_id, summary, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at''',
                (session_id, summary, self._now()),
            )
            conn.commit()

    def get_session_summary(self, session_id: str) -> str:
        with self._lock, self._connect() as conn:
            row = conn.execute('SELECT summary FROM session_summaries WHERE session_id=?', (session_id,)).fetchone()
        return str(row['summary']) if row else ''

    def remember(self, fact: str) -> str:
        fact = fact.strip()
        if not fact:
            return 'Nothing to remember.'
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

    def add_note(self, title: str, content: str) -> dict:
        title = title.strip()[:300] or 'Untitled note'
        content = content.strip()[:50000]
        if not content:
            raise ValueError('Note content is empty.')
        now = self._now()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO notes(title, content, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (title, content, now, now),
            )
            conn.commit()
            note_id = cur.lastrowid
        return {'id': note_id, 'title': title, 'content': content, 'created_at': now}

    def list_notes(self, limit: int = 30) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT id, title, content, created_at, updated_at FROM notes ORDER BY updated_at DESC LIMIT ?',
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def search_notes(self, query: str, limit: int = 20) -> list[dict]:
        query = query.strip()
        if not query:
            return self.list_notes(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT id, title, content, created_at, updated_at FROM notes
                   WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT ?''',
                (f'%{query}%', f'%{query}%', max(1, min(limit, 50))),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_todo(self, title: str) -> dict:
        title = title.strip()[:500]
        if not title:
            raise ValueError('Todo title is empty.')
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO todos(title, status, created_at) VALUES (?, ?, ?)',
                (title, 'open', self._now()),
            )
            conn.commit()
            todo_id = cur.lastrowid
        return {'id': todo_id, 'title': title, 'status': 'open'}

    def list_todos(self, include_done: bool = False, limit: int = 30) -> list[dict]:
        with self._lock, self._connect() as conn:
            if include_done:
                rows = conn.execute(
                    'SELECT * FROM todos ORDER BY id DESC LIMIT ?',
                    (max(1, min(limit, 100)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM todos WHERE status='open' ORDER BY id DESC LIMIT ?",
                    (max(1, min(limit, 100)),),
                ).fetchall()
        return [dict(r) for r in rows]

    def complete_todo(self, todo_id: int) -> dict:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE todos SET status='done', completed_at=? WHERE id=? AND status!='done'",
                (self._now(), int(todo_id)),
            )
            conn.commit()
        return {'id': int(todo_id), 'completed': cur.rowcount > 0}

    def add_reminder(self, text: str, due_at: str) -> dict:
        text = text.strip()[:1000]
        if not text:
            raise ValueError('Reminder text is empty.')
        try:
            due = datetime.fromisoformat(due_at)
        except ValueError as exc:
            raise ValueError('due_at must be ISO-8601, e.g. 2026-08-16T18:30:00+05:30') from exc
        if due.tzinfo is None:
            due = due.astimezone()
        due_utc = due.astimezone(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                'INSERT INTO reminders(text, due_at, status, created_at) VALUES (?, ?, ?, ?)',
                (text, due_utc, 'pending', self._now()),
            )
            conn.commit()
            reminder_id = cur.lastrowid
        return {'id': reminder_id, 'text': text, 'due_at': due_utc, 'status': 'pending'}

    def list_reminders(self, include_done: bool = False, limit: int = 30) -> list[dict]:
        with self._lock, self._connect() as conn:
            if include_done:
                rows = conn.execute('SELECT * FROM reminders ORDER BY due_at ASC LIMIT ?', (limit,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE status='pending' ORDER BY due_at ASC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def due_reminders(self, limit: int = 10) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status='pending' AND due_at<=? ORDER BY due_at ASC LIMIT ?",
                (now, max(1, min(limit, 50))),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminder_done(self, reminder_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET status='done', notified_at=? WHERE id=?",
                (self._now(), int(reminder_id)),
            )
            conn.commit()

    def agenda(self, limit: int = 20) -> dict:
        return {
            'open_todos': self.list_todos(False, limit),
            'pending_reminders': self.list_reminders(False, limit),
            'recent_notes': self.list_notes(min(limit, 10)),
        }

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
            notes = conn.execute('SELECT COUNT(*) FROM notes').fetchone()[0]
            summaries = conn.execute('SELECT COUNT(*) FROM session_summaries').fetchone()[0]
            docs = conn.execute('SELECT COUNT(*) FROM knowledge_docs').fetchone()[0]
            chunks = conn.execute('SELECT COUNT(*) FROM knowledge_chunks').fetchone()[0]
            todos = conn.execute("SELECT COUNT(*) FROM todos WHERE status='open'").fetchone()[0]
            reminders = conn.execute("SELECT COUNT(*) FROM reminders WHERE status='pending'").fetchone()[0]
        return {
            'sessions': sessions,
            'messages': messages,
            'facts': facts,
            'notes': notes,
            'session_summaries': summaries,
            'knowledge_docs': docs,
            'knowledge_chunks': chunks,
            'open_todos': todos,
            'pending_reminders': reminders,
        }

    def export_session(self, session_id: str, export_dir: Path) -> Path:
        export_dir.mkdir(parents=True, exist_ok=True)
        messages = self.session_messages(session_id, 2000)
        target = export_dir / f'jarvis-chat-{session_id}.md'
        lines = ['# JARVIS OMEGA Chat Export', '', f'Session: `{session_id}`', '']
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

    def _knowledge_rows(self, limit: int = 3000) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute('''
                SELECT kd.source, kc.chunk_index, kc.content
                FROM knowledge_chunks kc
                JOIN knowledge_docs kd ON kd.id = kc.doc_id
                ORDER BY kc.id DESC
                LIMIT ?
            ''', (max(1, min(limit, 10000)),)).fetchall()
        return [dict(r) for r in rows]

    def search_knowledge(self, query: str, limit: int = 6) -> list[dict]:
        terms = [t.lower() for t in re.findall(r'[\w-]{2,}', query, flags=re.UNICODE)][:12]
        if not terms:
            return []
        scored = []
        for row in self._knowledge_rows(3000):
            lowered = row['content'].lower()
            score = sum(lowered.count(term) for term in terms)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] | {'score': item[0]} for item in scored[:max(1, min(limit, 12))]]

    def vector_search_knowledge(self, query: str, limit: int = 8) -> list[dict]:
        """Local sparse-vector relevance search; no external embeddings/API required."""
        return rank_texts(query, self._knowledge_rows(3000), 'content', limit)
