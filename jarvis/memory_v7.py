from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import uuid4

from .memory import MemoryStore
from .retrieval import HybridRetriever, configured_embedding_backend
from .security.secrets import ensure_safe_for_persistent_memory
from .storage.migrations import SchemaMigrator


class MemoryKind(str, Enum):
    EPISODIC = 'EPISODIC'
    SEMANTIC = 'SEMANTIC'
    PROCEDURAL = 'PROCEDURAL'
    WORKING = 'WORKING'


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    kind: MemoryKind
    content: str
    key: str | None
    importance: float
    confidence: float
    source: str
    metadata: dict
    created_at: str
    updated_at: str
    last_verified: str | None


class V7MemoryStore(MemoryStore):
    """Backward-compatible V7 layered memory built beside the V6 tables."""

    def __init__(self, db_path: Path | None = None):
        super().__init__(db_path)
        self.migration_result = SchemaMigrator(self.db_path).migrate()
        self.retriever = HybridRetriever(configured_embedding_backend())

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, float(value)))

    def remember_v7(
        self,
        content: str,
        *,
        kind: MemoryKind | str = MemoryKind.SEMANTIC,
        key: str | None = None,
        importance: float = 0.5,
        confidence: float = 0.8,
        source: str = 'conversation',
        metadata: dict | None = None,
        verified: bool = False,
    ) -> dict:
        content = str(content).strip()[:12000]
        if not content:
            raise ValueError('Memory content is empty.')
        ensure_safe_for_persistent_memory(content)
        kind = MemoryKind(str(kind).upper()) if not isinstance(kind, MemoryKind) else kind
        key = (str(key).strip()[:300] if key else None) or None
        source = str(source or 'unknown').strip()[:200]
        metadata = dict(metadata or {})
        memory_id = uuid4().hex
        now = self._now()
        last_verified = now if verified else None

        with self._lock, self._connect() as conn:
            if key and kind in {MemoryKind.SEMANTIC, MemoryKind.PROCEDURAL}:
                old_rows = conn.execute(
                    '''SELECT id, content, confidence FROM v7_memories
                       WHERE kind=? AND memory_key=? AND active=1 ORDER BY updated_at DESC''',
                    (kind.value, key),
                ).fetchall()
                for row in old_rows:
                    if row['content'] == content:
                        new_conf = max(float(row['confidence']), self._clamp(confidence))
                        conn.execute(
                            '''UPDATE v7_memories SET confidence=?, importance=?, source=?, metadata_json=?,
                               updated_at=?, last_verified=COALESCE(?, last_verified) WHERE id=?''',
                            (
                                new_conf, self._clamp(importance), source,
                                json.dumps(metadata, ensure_ascii=False, default=str), now, last_verified, row['id'],
                            ),
                        )
                        conn.execute(
                            'INSERT INTO v7_memory_events(memory_id, event_type, detail_json, created_at) VALUES (?, ?, ?, ?)',
                            (row['id'], 'REINFORCED', json.dumps({'source': source}, ensure_ascii=False), now),
                        )
                        conn.commit()
                        return {'id': row['id'], 'updated': True, 'reinforced': True}
                    conn.execute('UPDATE v7_memories SET active=0, updated_at=? WHERE id=?', (now, row['id']))
                    conn.execute(
                        'INSERT INTO v7_memory_events(memory_id, event_type, detail_json, created_at) VALUES (?, ?, ?, ?)',
                        (row['id'], 'SUPERSEDED', json.dumps({'new_memory_id': memory_id}, ensure_ascii=False), now),
                    )

            conn.execute(
                '''INSERT INTO v7_memories(
                    id, kind, memory_key, content, importance, confidence, source,
                    metadata_json, active, created_at, updated_at, last_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)''',
                (
                    memory_id, kind.value, key, content, self._clamp(importance), self._clamp(confidence),
                    source, json.dumps(metadata, ensure_ascii=False, default=str), now, now, last_verified,
                ),
            )
            conn.execute(
                'INSERT INTO v7_memory_events(memory_id, event_type, detail_json, created_at) VALUES (?, ?, ?, ?)',
                (memory_id, 'CREATED', json.dumps({'source': source}, ensure_ascii=False), now),
            )
            conn.commit()
        return {'id': memory_id, 'updated': False, 'reinforced': False}

    def deactivate_memory(self, memory_id: str, reason: str = 'user_request') -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute('UPDATE v7_memories SET active=0, updated_at=? WHERE id=? AND active=1', (self._now(), memory_id))
            if cur.rowcount:
                conn.execute(
                    'INSERT INTO v7_memory_events(memory_id, event_type, detail_json, created_at) VALUES (?, ?, ?, ?)',
                    (memory_id, 'DEACTIVATED', json.dumps({'reason': reason}, ensure_ascii=False), self._now()),
                )
            conn.commit()
        return cur.rowcount > 0

    def verify_memory(self, memory_id: str, confidence: float | None = None) -> bool:
        now = self._now()
        with self._lock, self._connect() as conn:
            if confidence is None:
                cur = conn.execute('UPDATE v7_memories SET last_verified=?, updated_at=? WHERE id=? AND active=1', (now, now, memory_id))
            else:
                cur = conn.execute(
                    'UPDATE v7_memories SET confidence=?, last_verified=?, updated_at=? WHERE id=? AND active=1',
                    (self._clamp(confidence), now, now, memory_id),
                )
            if cur.rowcount:
                conn.execute(
                    'INSERT INTO v7_memory_events(memory_id, event_type, detail_json, created_at) VALUES (?, ?, ?, ?)',
                    (memory_id, 'VERIFIED', '{}', now),
                )
            conn.commit()
        return cur.rowcount > 0

    def _memory_rows(self, limit: int = 5000) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT id, kind, memory_key, content, importance, confidence, source,
                          metadata_json, created_at, updated_at, last_verified
                   FROM v7_memories WHERE active=1 ORDER BY updated_at DESC LIMIT ?''',
                (max(1, min(int(limit), 10000)),),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            try:
                item['metadata'] = json.loads(item.pop('metadata_json'))
            except Exception:
                item['metadata'] = {}
                item.pop('metadata_json', None)
            item['key'] = item.pop('memory_key')
            output.append(item)
        return output

    def search_memories(
        self,
        query: str,
        *,
        kinds: list[MemoryKind | str] | None = None,
        min_confidence: float = 0.0,
        limit: int = 8,
    ) -> list[dict]:
        allowed_kinds = None
        if kinds:
            allowed_kinds = {
                (item.value if isinstance(item, MemoryKind) else str(item).upper())
                for item in kinds
            }

        def filter_row(row: dict) -> bool:
            if float(row.get('confidence', 0.0)) < float(min_confidence):
                return False
            return allowed_kinds is None or row.get('kind') in allowed_kinds

        return self.retriever.rank(
            query,
            self._memory_rows(),
            text_key='content',
            limit=limit,
            metadata_filter=filter_row,
        )

    def set_working_memory(
        self,
        session_id: str,
        key: str,
        content: str,
        *,
        mission_id: str = '',
        metadata: dict | None = None,
    ) -> None:
        content = str(content).strip()[:20000]
        if not content:
            return
        ensure_safe_for_persistent_memory(content)
        with self._lock, self._connect() as conn:
            conn.execute(
                '''INSERT INTO v7_working_memory(session_id, mission_id, memory_key, content, metadata_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id, mission_id, memory_key) DO UPDATE SET
                     content=excluded.content, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at''',
                (
                    session_id, mission_id or '', key[:300], content,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str), self._now(),
                ),
            )
            conn.commit()

    def get_working_memory(self, session_id: str, mission_id: str = '') -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT memory_key, content, metadata_json, updated_at FROM v7_working_memory
                   WHERE session_id=? AND mission_id=? ORDER BY updated_at DESC''',
                (session_id, mission_id or ''),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            try:
                item['metadata'] = json.loads(item.pop('metadata_json'))
            except Exception:
                item['metadata'] = {}
                item.pop('metadata_json', None)
            output.append(item)
        return output

    def clear_working_memory(self, session_id: str, mission_id: str = '') -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute('DELETE FROM v7_working_memory WHERE session_id=? AND mission_id=?', (session_id, mission_id or ''))
            conn.commit()
        return cur.rowcount

    def remember(self, fact: str) -> str:
        ensure_safe_for_persistent_memory(fact)
        legacy = super().remember(fact)
        self.remember_v7(fact, kind=MemoryKind.SEMANTIC, confidence=0.75, source='legacy-remember')
        return legacy

    def add_note(self, title: str, content: str) -> dict:
        ensure_safe_for_persistent_memory(f'{title}\n{content}')
        return super().add_note(title, content)

    def add_todo(self, title: str) -> dict:
        ensure_safe_for_persistent_memory(title)
        return super().add_todo(title)

    def add_reminder(self, text: str, due_at: str) -> dict:
        ensure_safe_for_persistent_memory(text)
        return super().add_reminder(text, due_at)

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()

    def index_knowledge(self, source: str, text: str) -> dict:
        ensure_safe_for_persistent_memory(text)
        source = str(source).strip()[:1000]
        digest = self._content_hash(text)
        path = Path(source).expanduser()
        file_type = path.suffix.lower().lstrip('.') if path.suffix else None
        file_size = None
        modified_at = None
        if path.exists() and path.is_file():
            try:
                stat = path.stat()
                file_size = int(stat.st_size)
                modified_at = str(stat.st_mtime)
            except OSError:
                pass

        with self._lock, self._connect() as conn:
            row = conn.execute('SELECT content_hash, chunk_count FROM v7_document_index WHERE source=?', (source,)).fetchone()
            if row and row['content_hash'] == digest:
                return {'source': source, 'chunks': int(row['chunk_count']), 'duplicate_unchanged': True, 'content_hash': digest}

        result = super().index_knowledge(source, text)
        with self._lock, self._connect() as conn:
            conn.execute(
                '''INSERT INTO v7_document_index(source, content_hash, file_type, file_size, modified_at, indexed_at, chunk_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source) DO UPDATE SET
                     content_hash=excluded.content_hash, file_type=excluded.file_type,
                     file_size=excluded.file_size, modified_at=excluded.modified_at,
                     indexed_at=excluded.indexed_at, chunk_count=excluded.chunk_count''',
                (source, digest, file_type, file_size, modified_at, self._now(), int(result.get('chunks', 0))),
            )
            conn.commit()
        return result | {'content_hash': digest, 'duplicate_unchanged': False}

    def document_metadata(self, limit: int = 100) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM v7_document_index ORDER BY indexed_at DESC LIMIT ?',
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def hybrid_search_knowledge(self, query: str, limit: int = 8) -> list[dict]:
        rows = self._knowledge_rows(5000)
        normalized = [
            row | {
                'content': row.get('chunk', ''),
                'confidence': 0.75,
                'importance': 0.5,
            }
            for row in rows
        ]
        return self.retriever.rank(query, normalized, text_key='content', limit=limit)

    def v7_stats(self) -> dict:
        with self._lock, self._connect() as conn:
            memory_rows = conn.execute(
                'SELECT kind, COUNT(*) AS count FROM v7_memories WHERE active=1 GROUP BY kind'
            ).fetchall()
            working = conn.execute('SELECT COUNT(*) FROM v7_working_memory').fetchone()[0]
            docs = conn.execute('SELECT COUNT(*) FROM v7_document_index').fetchone()[0]
        return {
            'schema_version': SchemaMigrator(self.db_path).current_version(),
            'memory_layers': {row['kind']: row['count'] for row in memory_rows},
            'working_memory_items': working,
            'document_metadata_rows': docs,
            'embedding_reranker_configured': self.retriever.embedder is not None,
        }
