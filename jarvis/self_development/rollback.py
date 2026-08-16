from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RollbackCheckpoint:
    proposal_id: str
    before_sha: str
    deployed_sha: str | None
    status: str
    created_at: str
    updated_at: str
    reason: str = ''

    def as_dict(self) -> dict:
        return asdict(self)


class RollbackManager:
    """Persist known-good deployment checkpoints.

    This layer intentionally does not expose arbitrary ``git reset`` or filesystem
    deletion. The controlled release phase can attach a deployed commit and perform
    an approved revert using these immutable references.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_rollback_checkpoints (
                proposal_id TEXT PRIMARY KEY,
                before_sha TEXT NOT NULL,
                deployed_sha TEXT,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                checkpoint_json TEXT NOT NULL
            )''')
            conn.commit()

    def save(self, checkpoint: RollbackCheckpoint) -> None:
        payload = json.dumps(checkpoint.as_dict(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO v75_rollback_checkpoints(
                    proposal_id, before_sha, deployed_sha, status, reason, created_at, updated_at, checkpoint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    before_sha=excluded.before_sha,
                    deployed_sha=excluded.deployed_sha,
                    status=excluded.status,
                    reason=excluded.reason,
                    updated_at=excluded.updated_at,
                    checkpoint_json=excluded.checkpoint_json''',
                (
                    checkpoint.proposal_id, checkpoint.before_sha, checkpoint.deployed_sha,
                    checkpoint.status, checkpoint.reason, checkpoint.created_at,
                    checkpoint.updated_at, payload,
                ),
            )
            conn.commit()

    def create(self, proposal_id: str, before_sha: str) -> RollbackCheckpoint:
        now = _now()
        checkpoint = RollbackCheckpoint(proposal_id, before_sha, None, 'PREPARED', now, now)
        self.save(checkpoint)
        return checkpoint

    def mark_deployed(self, proposal_id: str, deployed_sha: str) -> RollbackCheckpoint:
        existing = self.get(proposal_id)
        if existing is None:
            raise KeyError(f'No rollback checkpoint for {proposal_id}.')
        checkpoint = RollbackCheckpoint(
            proposal_id=proposal_id,
            before_sha=existing.before_sha,
            deployed_sha=deployed_sha,
            status='DEPLOYED',
            created_at=existing.created_at,
            updated_at=_now(),
            reason=existing.reason,
        )
        self.save(checkpoint)
        return checkpoint

    def mark_rollback_required(self, proposal_id: str, reason: str) -> RollbackCheckpoint:
        existing = self.get(proposal_id)
        if existing is None:
            raise KeyError(f'No rollback checkpoint for {proposal_id}.')
        checkpoint = RollbackCheckpoint(
            proposal_id=proposal_id,
            before_sha=existing.before_sha,
            deployed_sha=existing.deployed_sha,
            status='ROLLBACK_REQUIRED',
            created_at=existing.created_at,
            updated_at=_now(),
            reason=str(reason)[:2000],
        )
        self.save(checkpoint)
        return checkpoint

    def get(self, proposal_id: str) -> RollbackCheckpoint | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT checkpoint_json FROM v75_rollback_checkpoints WHERE proposal_id=?',
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        raw = json.loads(row['checkpoint_json'])
        return RollbackCheckpoint(**raw)
