from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionStatus(str, Enum):
    IDLE = 'IDLE'
    UNDERSTANDING = 'UNDERSTANDING'
    PLANNING = 'PLANNING'
    WAITING_FOR_PERMISSION = 'WAITING_FOR_PERMISSION'
    EXECUTING = 'EXECUTING'
    VERIFYING = 'VERIFYING'
    RECOVERING = 'RECOVERING'
    REPLANNING = 'REPLANNING'
    PAUSED = 'PAUSED'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


class StepStatus(str, Enum):
    PENDING = 'PENDING'
    EXECUTING = 'EXECUTING'
    VERIFYING = 'VERIFYING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


@dataclass
class VerificationResult:
    verified: bool
    status: str
    summary: str
    evidence: list[dict] = field(default_factory=list)
    unverified_actions: list[str] = field(default_factory=list)


@dataclass
class MissionStep:
    index: int
    description: str
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    result: str = ''
    error: str = ''
    tool_events: list[dict] = field(default_factory=list)
    verification: VerificationResult | None = None
    recovered: bool = False
    recovered_by: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class Mission:
    goal: str
    session_id: str
    id: str = field(default_factory=lambda: f'MSN-{uuid4().hex[:10].upper()}')
    status: MissionStatus = MissionStatus.IDLE
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    plan: list[MissionStep] = field(default_factory=list)
    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    retry_count: int = 0
    recovery_count: int = 0
    permissions: dict = field(default_factory=dict)
    results: list[dict] = field(default_factory=list)
    final_verification: VerificationResult | None = None
    final_report: str = ''
    last_error: str = ''

    def touch(self, status: MissionStatus | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = utc_now()

    def to_dict(self) -> dict:
        value = asdict(self)
        value['status'] = self.status.value
        for step in value['plan']:
            if hasattr(step.get('status'), 'value'):
                step['status'] = step['status'].value
        return value

    @classmethod
    def from_dict(cls, data: dict) -> 'Mission':
        plan: list[MissionStep] = []
        for raw in data.get('plan', []):
            item = dict(raw)
            item['status'] = StepStatus(item.get('status', StepStatus.PENDING.value))
            verification = item.get('verification')
            if isinstance(verification, dict):
                item['verification'] = VerificationResult(**verification)
            plan.append(MissionStep(**item))
        final_verification = data.get('final_verification')
        if isinstance(final_verification, dict):
            final_verification = VerificationResult(**final_verification)
        return cls(
            id=data.get('id') or f'MSN-{uuid4().hex[:10].upper()}',
            goal=data.get('goal', ''),
            session_id=data.get('session_id', ''),
            status=MissionStatus(data.get('status', MissionStatus.IDLE.value)),
            created_at=data.get('created_at', utc_now()),
            updated_at=data.get('updated_at', utc_now()),
            plan=plan,
            current_step=int(data.get('current_step', 0)),
            completed_steps=list(data.get('completed_steps', [])),
            failed_steps=list(data.get('failed_steps', [])),
            retry_count=int(data.get('retry_count', 0)),
            recovery_count=int(data.get('recovery_count', 0)),
            permissions=dict(data.get('permissions', {})),
            results=list(data.get('results', [])),
            final_verification=final_verification,
            final_report=data.get('final_report', ''),
            last_error=data.get('last_error', ''),
        )
