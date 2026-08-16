from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    text = re.sub(r'[^a-z0-9]+', '_', str(value).strip().lower()).strip('_')
    return text[:80] or 'unnamed_skill'


class SkillProposalStatus(str, Enum):
    PROPOSED = 'PROPOSED'
    BUILDING = 'BUILDING'
    TESTED = 'TESTED'
    SECURITY_REVIEW = 'SECURITY_REVIEW'
    AWAITING_APPROVAL = 'AWAITING_APPROVAL'
    ACTIVE = 'ACTIVE'
    REJECTED = 'REJECTED'
    DISABLED = 'DISABLED'
    FAILED = 'FAILED'


@dataclass(frozen=True)
class SkillManifest:
    name: str
    slug: str
    version: str
    description: str
    permissions: tuple[str, ...]
    risk: str
    implementation: str
    tests: tuple[str, ...]
    documentation: str
    evaluation: str

    def validate(self) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if not self.name.strip():
            reasons.append('name is required')
        if self.slug != _slug(self.slug):
            reasons.append('slug must be normalized lowercase snake_case')
        if not re.fullmatch(r'\d+\.\d+\.\d+', self.version):
            reasons.append('version must be semantic x.y.z')
        if not self.description.strip():
            reasons.append('description is required')
        if not self.implementation.startswith(f'skills/{self.slug}/'):
            reasons.append('implementation must live inside the skill directory')
        if not self.tests or any(not path.startswith(f'skills/{self.slug}/') for path in self.tests):
            reasons.append('tests must be declared inside the skill directory')
        if not self.documentation.startswith(f'skills/{self.slug}/'):
            reasons.append('documentation must live inside the skill directory')
        if not self.evaluation.startswith(f'skills/{self.slug}/'):
            reasons.append('evaluation metadata must live inside the skill directory')
        return not reasons, tuple(reasons)

    def as_dict(self) -> dict:
        data = asdict(self)
        data['permissions'] = list(self.permissions)
        data['tests'] = list(self.tests)
        return data


@dataclass
class SkillProposal:
    manifest: SkillManifest
    problem: str
    objective: str
    evidence: list[str]
    id: str = field(default_factory=lambda: f'SKILL-{uuid4().hex[:10].upper()}')
    status: SkillProposalStatus = SkillProposalStatus.PROPOSED
    source_gap_id: str | None = None
    improvement_proposal_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'manifest': self.manifest.as_dict(),
            'problem': self.problem,
            'objective': self.objective,
            'evidence': list(self.evidence),
            'status': self.status.value,
            'source_gap_id': self.source_gap_id,
            'improvement_proposal_id': self.improvement_proposal_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> 'SkillProposal':
        manifest_raw = dict(raw['manifest'])
        manifest_raw['permissions'] = tuple(manifest_raw.get('permissions') or ())
        manifest_raw['tests'] = tuple(manifest_raw.get('tests') or ())
        return cls(
            manifest=SkillManifest(**manifest_raw),
            problem=raw['problem'],
            objective=raw['objective'],
            evidence=list(raw.get('evidence') or []),
            id=raw['id'],
            status=SkillProposalStatus(raw.get('status', 'PROPOSED')),
            source_gap_id=raw.get('source_gap_id'),
            improvement_proposal_id=raw.get('improvement_proposal_id'),
            created_at=raw.get('created_at') or _now(),
            updated_at=raw.get('updated_at') or _now(),
        )


class SkillRegistry:
    """Persists skill proposals and validates manifests without auto-activating code."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_skill_proposals (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL,
                status TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_skill_status ON v75_skill_proposals(status, updated_at)')
            conn.commit()

    @staticmethod
    def manifest_for_gap(gap: dict) -> SkillManifest:
        capability = str(gap.get('capability') or gap.get('title') or 'New Capability')
        title = str(gap.get('title') or capability)
        slug = _slug(capability if not capability.startswith('Tool:') else capability.split(':', 1)[1])
        permissions = tuple(sorted({str(item) for item in gap.get('permissions', []) if str(item).strip()}))
        return SkillManifest(
            name=title[:120],
            slug=slug,
            version='0.1.0',
            description=str(gap.get('description') or f'Reusable skill proposed to address {title}.')[:1000],
            permissions=permissions,
            risk=str(gap.get('severity') or 'MEDIUM'),
            implementation=f'skills/{slug}/implementation.py',
            tests=(f'skills/{slug}/tests/test_skill.py',),
            documentation=f'skills/{slug}/README.md',
            evaluation=f'skills/{slug}/evaluation.json',
        )

    def propose_from_gap(self, gap: dict) -> SkillProposal:
        manifest = self.manifest_for_gap(gap)
        valid, reasons = manifest.validate()
        if not valid:
            raise ValueError('Invalid generated skill manifest: ' + '; '.join(reasons))
        proposal = SkillProposal(
            manifest=manifest,
            problem=str(gap.get('description') or 'Capability gap requires a reusable skill.')[:4000],
            objective=str(gap.get('recommended_action') or f'Build and verify {manifest.name} as a reusable skill.')[:4000],
            evidence=[str(item)[:1000] for item in gap.get('evidence', [])][:30],
            source_gap_id=str(gap.get('id') or '') or None,
        )
        self.save(proposal)
        return proposal

    def link_improvement(self, skill_id: str, improvement_proposal_id: str) -> SkillProposal:
        proposal = self.get(skill_id)
        if proposal is None:
            raise KeyError(skill_id)
        proposal.improvement_proposal_id = improvement_proposal_id
        proposal.status = SkillProposalStatus.BUILDING
        proposal.updated_at = _now()
        self.save(proposal)
        return proposal

    def save(self, proposal: SkillProposal) -> None:
        valid, reasons = proposal.manifest.validate()
        if not valid:
            raise ValueError('Invalid skill manifest: ' + '; '.join(reasons))
        proposal.updated_at = _now()
        payload = json.dumps(proposal.as_dict(), ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO v75_skill_proposals(id, slug, status, proposal_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, status=excluded.status,
                   proposal_json=excluded.proposal_json, updated_at=excluded.updated_at''',
                (proposal.id, proposal.manifest.slug, proposal.status.value, payload, proposal.created_at, proposal.updated_at),
            )
            conn.commit()

    def get(self, skill_id: str) -> SkillProposal | None:
        with self._connect() as conn:
            row = conn.execute('SELECT proposal_json FROM v75_skill_proposals WHERE id=?', (skill_id,)).fetchone()
        return SkillProposal.from_dict(json.loads(row['proposal_json'])) if row else None

    def recent(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT proposal_json FROM v75_skill_proposals ORDER BY updated_at DESC LIMIT ?', (limit,)
            ).fetchall()
        return [json.loads(row['proposal_json']) for row in rows]
