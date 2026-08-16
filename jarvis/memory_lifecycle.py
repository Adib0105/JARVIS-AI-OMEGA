from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings
from .storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MemoryContradiction:
    stable_key: str
    memory_ids: tuple[str, ...]
    contents: tuple[str, ...]
    confidences: tuple[float, ...]

    def as_dict(self) -> dict:
        return {
            'stable_key': self.stable_key,
            'memory_ids': list(self.memory_ids),
            'contents': list(self.contents),
            'confidences': list(self.confidences),
        }


class MemoryLifecycleManager:
    """Additive lifecycle operations for the existing V7 memory table.

    The manager validates the live schema before writing. It never invents a migration
    when required columns are missing and never stores new secret content itself.
    """

    TABLE = 'v7_memories'
    REQUIRED = {'id', 'content', 'confidence', 'updated_at', 'status'}

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_links()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _columns(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(f'PRAGMA table_info({self.TABLE})').fetchall()
        return {str(row['name']) for row in rows}

    def _require_schema(self) -> set[str]:
        columns = self._columns()
        missing = self.REQUIRED - columns
        if missing:
            raise RuntimeError(f'V7 memory lifecycle requires columns: {sorted(missing)}')
        return columns

    def _init_links(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_memory_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relation TEXT NOT NULL,
                from_memory_id TEXT NOT NULL,
                to_memory_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_memory_rel_from ON v75_memory_relations(from_memory_id, relation)')
            conn.commit()

    def reinforce(self, memory_id, *, amount: float = 0.05, verified: bool = True) -> dict:
        columns = self._require_schema()
        amount = max(0.0, min(float(amount), 0.25))
        now = _now()
        sets = ['confidence=MIN(1.0, MAX(0.0, confidence + ?))', 'updated_at=?']
        params = [amount, now]
        if verified and 'last_verified' in columns:
            sets.append('last_verified=?'); params.append(now)
        if 'status' in columns:
            sets.append("status=CASE WHEN status IN ('STALE','stale') THEN 'ACTIVE' ELSE status END")
        params.append(memory_id)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE {self.TABLE} SET {', '.join(sets)} WHERE id=?", tuple(params))
            conn.commit()
            row = conn.execute(f'SELECT * FROM {self.TABLE} WHERE id=?', (memory_id,)).fetchone()
        if cur.rowcount == 0 or row is None:
            raise KeyError(memory_id)
        return dict(row)

    def supersede(self, old_memory_id, new_memory_id, *, reason: str = 'newer verified memory') -> dict:
        columns = self._require_schema()
        now = _now()
        with self._connect() as conn:
            old = conn.execute(f'SELECT id FROM {self.TABLE} WHERE id=?', (old_memory_id,)).fetchone()
            new = conn.execute(f'SELECT id FROM {self.TABLE} WHERE id=?', (new_memory_id,)).fetchone()
            if old is None or new is None:
                raise KeyError('Both old and new memory IDs must exist.')
            conn.execute(
                f"UPDATE {self.TABLE} SET status='SUPERSEDED', updated_at=? WHERE id=?",
                (now, old_memory_id),
            )
            if 'last_verified' in columns:
                conn.execute(
                    f"UPDATE {self.TABLE} SET status='ACTIVE', updated_at=?, last_verified=? WHERE id=?",
                    (now, now, new_memory_id),
                )
            else:
                conn.execute(
                    f"UPDATE {self.TABLE} SET status='ACTIVE', updated_at=? WHERE id=?",
                    (now, new_memory_id),
                )
            conn.execute(
                '''INSERT INTO v75_memory_relations(relation, from_memory_id, to_memory_id, reason, created_at)
                   VALUES ('SUPERSEDES', ?, ?, ?, ?)''',
                (str(new_memory_id), str(old_memory_id), str(reason)[:1000], now),
            )
            conn.commit()
        return {'old_memory_id': old_memory_id, 'new_memory_id': new_memory_id, 'status': 'SUPERSEDED', 'reason': reason}

    @staticmethod
    def _normalized_content(value: str) -> str:
        return ' '.join(str(value).strip().casefold().split())

    def contradictions(self, *, limit: int = 100) -> list[MemoryContradiction]:
        columns = self._require_schema()
        if 'stable_key' not in columns:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                f'''SELECT id, stable_key, content, confidence FROM {self.TABLE}
                    WHERE stable_key IS NOT NULL AND TRIM(stable_key)!=''
                      AND UPPER(status) NOT IN ('SUPERSEDED','DELETED')
                    ORDER BY updated_at DESC LIMIT ?''',
                (max(2, min(int(limit) * 10, 1000)),),
            ).fetchall()
        grouped: dict[str, list] = {}
        for row in rows:
            grouped.setdefault(str(row['stable_key']), []).append(row)
        output: list[MemoryContradiction] = []
        for key, items in grouped.items():
            normalized = {self._normalized_content(row['content']) for row in items}
            if len(items) < 2 or len(normalized) < 2:
                continue
            output.append(MemoryContradiction(
                stable_key=key,
                memory_ids=tuple(str(row['id']) for row in items),
                contents=tuple(str(row['content']) for row in items),
                confidences=tuple(float(row['confidence']) for row in items),
            ))
            if len(output) >= limit:
                break
        return output

    def decay_stale(
        self,
        *,
        older_than_days: int = 90,
        decay: float = 0.05,
        stale_below: float = 0.35,
        kinds: tuple[str, ...] = ('SEMANTIC',),
    ) -> dict:
        columns = self._require_schema()
        reference_col = 'last_verified' if 'last_verified' in columns else 'updated_at'
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(older_than_days)))).isoformat()
        decay = max(0.0, min(float(decay), 0.25))
        where = [f"COALESCE({reference_col}, updated_at) < ?", "UPPER(status) NOT IN ('SUPERSEDED','DELETED')"]
        params: list = [cutoff]
        if 'kind' in columns and kinds:
            placeholders = ','.join('?' for _ in kinds)
            where.append(f'UPPER(kind) IN ({placeholders})')
            params.extend([str(item).upper() for item in kinds])
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                f'''UPDATE {self.TABLE}
                    SET confidence=MAX(0.0, confidence - ?),
                        status=CASE WHEN MAX(0.0, confidence - ?) < ? THEN 'STALE' ELSE status END,
                        updated_at=?
                    WHERE {' AND '.join(where)}''',
                (decay, decay, float(stale_below), now, *params),
            )
            conn.commit()
        return {
            'updated': cur.rowcount,
            'cutoff': cutoff,
            'decay': decay,
            'stale_below': stale_below,
            'kinds': list(kinds),
        }

    def relations(self, memory_id=None, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            if memory_id is None:
                rows = conn.execute(
                    'SELECT * FROM v75_memory_relations ORDER BY id DESC LIMIT ?',
                    (max(1, min(int(limit), 500)),),
                ).fetchall()
            else:
                rows = conn.execute(
                    '''SELECT * FROM v75_memory_relations
                       WHERE from_memory_id=? OR to_memory_id=? ORDER BY id DESC LIMIT ?''',
                    (str(memory_id), str(memory_id), max(1, min(int(limit), 500))),
                ).fetchall()
        return [dict(row) for row in rows]
