from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


TARGET_SCHEMA_VERSION = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SchemaMigrator:
    """Additive SQLite migrations. V7 never silently deletes legacy V6 data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_meta(self, conn: sqlite3.Connection) -> None:
        conn.execute('''CREATE TABLE IF NOT EXISTS jarvis_schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')

    def current_version(self) -> int:
        if not self.db_path.exists():
            return 0
        with self._connect() as conn:
            self._ensure_meta(conn)
            row = conn.execute("SELECT value FROM jarvis_schema_meta WHERE key='schema_version'").fetchone()
            if not row:
                return 6
            try:
                return int(row['value'])
            except (TypeError, ValueError):
                return 6

    def _backup_legacy_once(self) -> Path | None:
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return None
        backup_dir = self.db_path.parent / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f'{self.db_path.stem}-pre-v7{self.db_path.suffix}.bak'
        if target.exists():
            return target
        shutil.copy2(self.db_path, target)
        return target

    @staticmethod
    def _set_version(conn: sqlite3.Connection, version: int) -> None:
        conn.execute(
            '''INSERT INTO jarvis_schema_meta(key, value, updated_at) VALUES ('schema_version', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at''',
            (str(version), _now()),
        )

    def migrate(self) -> dict:
        previous = self.current_version()
        backup = None
        if previous < TARGET_SCHEMA_VERSION:
            backup = self._backup_legacy_once()

        with self._connect() as conn:
            self._ensure_meta(conn)
            if previous < 7:
                self._migration_7(conn)
                self._set_version(conn, 7)
            conn.commit()

        return {
            'previous_version': previous,
            'current_version': self.current_version(),
            'backup': str(backup) if backup else None,
        }

    @staticmethod
    def _migration_7(conn: sqlite3.Connection) -> None:
        conn.execute('''CREATE TABLE IF NOT EXISTS v7_memories (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            memory_key TEXT,
            content TEXT NOT NULL,
            importance REAL NOT NULL DEFAULT 0.5,
            confidence REAL NOT NULL DEFAULT 0.7,
            source TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_verified TEXT
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_memory_kind ON v7_memories(kind, active, updated_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_memory_key ON v7_memories(memory_key, active)')
        conn.execute('''CREATE TABLE IF NOT EXISTS v7_memory_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_memory_events ON v7_memory_events(memory_id, id)')
        conn.execute('''CREATE TABLE IF NOT EXISTS v7_document_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL UNIQUE,
            content_hash TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            modified_at TEXT,
            indexed_at TEXT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_document_hash ON v7_document_index(content_hash)')
        # Working memory is intentionally separated from long-lived semantic memory.
        conn.execute('''CREATE TABLE IF NOT EXISTS v7_working_memory (
            session_id TEXT NOT NULL,
            mission_id TEXT NOT NULL DEFAULT '',
            memory_key TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL,
            PRIMARY KEY(session_id, mission_id, memory_key)
        )''')
