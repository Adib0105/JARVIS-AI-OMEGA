from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DocumentIndexDecision:
    action: str
    source: str
    content_hash: str
    duplicate_of: str | None = None
    previous_hash: str | None = None
    chunks: int | None = None

    def as_dict(self) -> dict:
        return {
            'action': self.action,
            'source': self.source,
            'content_hash': self.content_hash,
            'duplicate_of': self.duplicate_of,
            'previous_hash': self.previous_hash,
            'chunks': self.chunks,
        }


class DocumentIndexStore:
    """Additive V7.5 provenance/hash registry around the legacy knowledge tables."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_document_index (
                source TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                status TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_doc_hash ON v75_document_index(content_hash, status)')
            conn.commit()

    def decide(self, source: str, content_hash: str) -> DocumentIndexDecision:
        source = str(source)
        content_hash = str(content_hash)
        with self._connect() as conn:
            same_source = conn.execute(
                'SELECT content_hash, chunks, status FROM v75_document_index WHERE source=?', (source,)
            ).fetchone()
            duplicate = conn.execute(
                "SELECT source, chunks FROM v75_document_index WHERE content_hash=? AND source!=? AND status='active' ORDER BY updated_at DESC LIMIT 1",
                (content_hash, source),
            ).fetchone()
        if same_source and same_source['content_hash'] == content_hash and same_source['status'] == 'active':
            return DocumentIndexDecision('UNCHANGED', source, content_hash, chunks=int(same_source['chunks']))
        if duplicate:
            return DocumentIndexDecision(
                'DUPLICATE', source, content_hash,
                duplicate_of=str(duplicate['source']), chunks=int(duplicate['chunks']),
                previous_hash=str(same_source['content_hash']) if same_source else None,
            )
        if same_source:
            return DocumentIndexDecision(
                'UPDATE', source, content_hash,
                previous_hash=str(same_source['content_hash']), chunks=int(same_source['chunks']),
            )
        return DocumentIndexDecision('INDEX', source, content_hash)

    def record(
        self,
        *,
        source: str,
        content_hash: str,
        size_bytes: int,
        mtime_ns: int,
        chunks: int,
        metadata: dict,
        status: str = 'active',
    ) -> None:
        now = _now()
        payload = json.dumps(metadata, ensure_ascii=False, default=str)
        with self._connect() as conn:
            existing = conn.execute('SELECT indexed_at FROM v75_document_index WHERE source=?', (source,)).fetchone()
            indexed_at = str(existing['indexed_at']) if existing else now
            conn.execute(
                '''INSERT INTO v75_document_index(
                    source, content_hash, size_bytes, mtime_ns, chunks, metadata_json,
                    status, indexed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    chunks=excluded.chunks,
                    metadata_json=excluded.metadata_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at''',
                (
                    source, content_hash, int(size_bytes), int(mtime_ns), int(chunks), payload,
                    status, indexed_at, now,
                ),
            )
            conn.commit()

    def mark_missing(self, source: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE v75_document_index SET status='missing', updated_at=? WHERE source=? AND status!='missing'",
                (_now(), str(source)),
            )
            conn.commit()
            return cur.rowcount > 0

    def get(self, source: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM v75_document_index WHERE source=?', (str(source),)).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item['metadata'] = json.loads(item.pop('metadata_json'))
        except Exception:
            item['metadata'] = {}
            item.pop('metadata_json', None)
        return item

    def stale_sources(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source, content_hash, updated_at FROM v75_document_index WHERE status='missing' ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
        return [dict(row) for row in rows]
