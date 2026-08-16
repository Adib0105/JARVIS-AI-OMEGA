from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProposalStatus(str, Enum):
    PROPOSED = 'PROPOSED'
    SANDBOX_READY = 'SANDBOX_READY'
    TESTING = 'TESTING'
    TESTED = 'TESTED'
    EVALUATED = 'EVALUATED'
    SECURITY_REVIEW = 'SECURITY_REVIEW'
    AWAITING_APPROVAL = 'AWAITING_APPROVAL'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    DEPLOYED = 'DEPLOYED'
    ROLLED_BACK = 'ROLLED_BACK'
    FAILED = 'FAILED'


@dataclass
class ImprovementProposal:
    title: str
    capability: str
    problem: str
    objective: str
    evidence: list[str]
    id: str = field(default_factory=lambda: f'IMP-{uuid4().hex[:8].upper()}')
    status: ProposalStatus = ProposalStatus.PROPOSED
    risk: str = 'MEDIUM'
    source_gap_id: str | None = None
    branch: str = ''
    sandbox_path: str = ''
    plan: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    test_summary: dict = field(default_factory=dict)
    evaluation_summary: dict = field(default_factory=dict)
    policy_summary: dict = field(default_factory=dict)
    diff_summary: str = ''
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def touch(self, status: ProposalStatus | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = _now()

    def as_dict(self) -> dict:
        value = asdict(self)
        value['status'] = self.status.value
        return value

    @classmethod
    def from_dict(cls, raw: dict) -> 'ImprovementProposal':
        data = dict(raw)
        data['status'] = ProposalStatus(data.get('status', ProposalStatus.PROPOSED.value))
        return cls(**data)


class ProposalStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_improvement_proposals (
                id TEXT PRIMARY KEY,
                capability TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_proposals_status ON v75_improvement_proposals(status, updated_at)')
            conn.commit()

    def save(self, proposal: ImprovementProposal) -> None:
        proposal.touch()
        payload = json.dumps(proposal.as_dict(), ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO v75_improvement_proposals(id, capability, title, status, proposal_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     capability=excluded.capability,
                     title=excluded.title,
                     status=excluded.status,
                     proposal_json=excluded.proposal_json,
                     updated_at=excluded.updated_at''',
                (proposal.id, proposal.capability, proposal.title, proposal.status.value, payload, proposal.created_at, proposal.updated_at),
            )
            conn.commit()

    def get(self, proposal_id: str) -> ImprovementProposal | None:
        with self._connect() as conn:
            row = conn.execute('SELECT proposal_json FROM v75_improvement_proposals WHERE id=?', (proposal_id,)).fetchone()
        if not row:
            return None
        return ImprovementProposal.from_dict(json.loads(row['proposal_json']))

    def list_recent(self, limit: int = 50, status: ProposalStatus | None = None) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    'SELECT proposal_json FROM v75_improvement_proposals ORDER BY updated_at DESC LIMIT ?', (limit,)
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT proposal_json FROM v75_improvement_proposals WHERE status=? ORDER BY updated_at DESC LIMIT ?',
                    (status.value, limit),
                ).fetchall()
        return [json.loads(row['proposal_json']) for row in rows]
