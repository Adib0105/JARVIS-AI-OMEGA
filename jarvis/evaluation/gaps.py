from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from ..agent.mission import MissionStatus
from ..agent.mission_store import MissionStore
from ..capability_registry import CapabilityRegistry, CapabilityStatus
from ..config import settings
from ..security.audit import AuditStore
from ..storage.sqlite_utils import connect_sqlite
from .engine import EvaluationSnapshot, SelfEvaluationEngine


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GapSeverity(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


@dataclass(frozen=True)
class CapabilityGap:
    id: str
    capability: str
    title: str
    description: str
    severity: GapSeverity
    source: str
    evidence: tuple[str, ...]
    recommended_action: str
    created_at: str
    status: str = 'OPEN'

    def as_dict(self) -> dict:
        data = asdict(self)
        data['severity'] = self.severity.value
        data['evidence'] = list(self.evidence)
        return data


class CapabilityGapDetector:
    """Detect engineering gaps from persisted/runtime evidence.

    A gap is a proposal input, never an automatic production change. Detection is
    intentionally deterministic and does not use an LLM to manufacture evidence.
    """

    METRIC_TARGETS = {
        'mission_success_rate': (0.90, 'Mission Reliability'),
        'tool_success_rate': (0.95, 'Tool Runtime'),
        'verification_success_rate': (0.90, 'Verification'),
        'recovery_success_rate': (0.80, 'Recovery'),
        'replanning_success_rate': (0.80, 'Replanning'),
        'browser_success_rate': (0.90, 'Browser'),
        'computer_use_success_rate': (0.90, 'Computer Use'),
        'tool_verification_success_rate': (0.90, 'Tool Verification'),
    }

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        evaluation: SelfEvaluationEngine | None = None,
        missions: MissionStore | None = None,
        audit: AuditStore | None = None,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry or CapabilityRegistry()
        self.missions = missions or MissionStore(self.db_path)
        self.audit = audit or AuditStore(self.db_path)
        self.evaluation = evaluation or SelfEvaluationEngine(
            self.db_path,
            mission_store=self.missions,
            audit_store=self.audit,
            capability_registry=self.registry,
        )
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_capability_gaps (
                id TEXT PRIMARY KEY,
                capability TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                source TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                gap_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL
            )''')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_v75_gap_fingerprint ON v75_capability_gaps(fingerprint)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_gap_status ON v75_capability_gaps(status, updated_at)')
            conn.commit()

    @staticmethod
    def _severity_for_status(status: CapabilityStatus) -> GapSeverity:
        return {
            CapabilityStatus.BROKEN: GapSeverity.CRITICAL,
            CapabilityStatus.MISSING: GapSeverity.HIGH,
            CapabilityStatus.DEGRADED: GapSeverity.MEDIUM,
            CapabilityStatus.EXPERIMENTAL: GapSeverity.LOW,
        }.get(status, GapSeverity.LOW)

    @staticmethod
    def _metric_severity(value: float, target: float) -> GapSeverity:
        gap = target - value
        if gap >= 0.40:
            return GapSeverity.CRITICAL
        if gap >= 0.20:
            return GapSeverity.HIGH
        if gap >= 0.08:
            return GapSeverity.MEDIUM
        return GapSeverity.LOW

    @staticmethod
    def _make(
        capability: str,
        title: str,
        description: str,
        severity: GapSeverity,
        source: str,
        evidence: list[str],
        recommended_action: str,
    ) -> CapabilityGap:
        return CapabilityGap(
            id=f'GAP-{uuid4().hex[:10].upper()}',
            capability=capability,
            title=title,
            description=description,
            severity=severity,
            source=source,
            evidence=tuple(evidence[:20]),
            recommended_action=recommended_action,
            created_at=_now(),
        )

    def _registry_gaps(self) -> list[CapabilityGap]:
        output: list[CapabilityGap] = []
        for raw in self.registry.snapshot():
            status = CapabilityStatus(raw['status'])
            if status not in {CapabilityStatus.MISSING, CapabilityStatus.BROKEN, CapabilityStatus.DEGRADED}:
                continue
            name = raw['name']
            detail = raw.get('detail') or 'runtime registry reports reduced capability'
            output.append(self._make(
                name,
                f'{name} is {status.value}',
                f'Runtime capability registry reports {name} as {status.value}.',
                self._severity_for_status(status),
                'capability_registry',
                [detail, f"implementation: {raw.get('implementation_path', '')}"],
                'Inspect missing dependencies/configuration or implement the absent subsystem; verify with dedicated tests before activation.',
            ))
        return output

    def _metric_gaps(self, snapshot: EvaluationSnapshot) -> list[CapabilityGap]:
        output: list[CapabilityGap] = []
        for metric_name, (target, capability) in self.METRIC_TARGETS.items():
            metric = snapshot.metrics.get(metric_name)
            if metric is None or metric.value is None or not metric.denominator:
                continue
            if metric.value >= target:
                continue
            output.append(self._make(
                capability,
                f'{capability} score below target',
                f'{metric_name} is below the evidence-based target.',
                self._metric_severity(metric.value, target),
                'self_evaluation',
                [
                    f'metric={metric_name}',
                    f'value={metric.value:.4f}',
                    f'target={target:.4f}',
                    f'samples={metric.denominator}',
                ],
                f'Inspect failure examples for {metric_name}, add regression cases, improve the subsystem in sandbox, then compare before/after evaluation.',
            ))
        return output

    def _repeated_tool_failure_gaps(self, audit_limit: int) -> list[CapabilityGap]:
        rows = self.audit.list_entries(limit=audit_limit)
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            if row.get('execution_status') != 'FAILED':
                continue
            key = (str(row.get('tool_name') or 'unknown'), str(row.get('error_type') or 'UNKNOWN'))
            grouped.setdefault(key, []).append(row)
        output: list[CapabilityGap] = []
        for (tool_name, error_type), failures in grouped.items():
            if len(failures) < 3:
                continue
            output.append(self._make(
                f'Tool:{tool_name}',
                f'Repeated {tool_name} failures',
                f'{tool_name} failed {len(failures)} times with the same normalized error category.',
                GapSeverity.HIGH if len(failures) >= 5 else GapSeverity.MEDIUM,
                'audit_log',
                [f'error_type={error_type}', f'failure_count={len(failures)}'],
                'Reproduce the repeated failure with a deterministic test, inspect the tool implementation/dependencies, and repair the root cause.',
            ))
        return output

    def _failed_mission_gaps(self, mission_limit: int) -> list[CapabilityGap]:
        rows = self.missions.list_recent(mission_limit)
        failed = []
        for row in rows:
            mission = self.missions.get(row['id'])
            if mission and mission.status == MissionStatus.FAILED:
                failed.append(mission)
        groups: dict[str, list] = {}
        for mission in failed:
            key = (mission.last_error or 'unknown failure').strip().lower()[:180]
            groups.setdefault(key, []).append(mission)
        output: list[CapabilityGap] = []
        for normalized_error, missions in groups.items():
            if len(missions) < 2:
                continue
            output.append(self._make(
                'Mission Reliability',
                'Repeated mission failure pattern',
                f'{len(missions)} recent missions failed with the same normalized blocker.',
                GapSeverity.HIGH if len(missions) >= 4 else GapSeverity.MEDIUM,
                'mission_history',
                [f'blocker={normalized_error}', f'count={len(missions)}'] + [f'goal={m.goal[:120]}' for m in missions[:5]],
                'Create a minimized regression scenario for this blocker and improve planner/tool/recovery behavior without weakening permissions.',
            ))
        return output

    @staticmethod
    def _fingerprint(gap: CapabilityGap) -> str:
        base = f'{gap.capability}|{gap.title}|{gap.source}'.lower()
        import hashlib
        return hashlib.sha256(base.encode('utf-8')).hexdigest()

    def persist(self, gaps: list[CapabilityGap]) -> None:
        now = _now()
        with self._connect() as conn:
            for gap in gaps:
                fingerprint = self._fingerprint(gap)
                payload = json.dumps(gap.as_dict(), ensure_ascii=False, default=str)
                conn.execute(
                    '''INSERT INTO v75_capability_gaps(
                        id, capability, title, severity, source, fingerprint, gap_json,
                        created_at, updated_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        severity=excluded.severity,
                        gap_json=excluded.gap_json,
                        updated_at=excluded.updated_at,
                        status='OPEN' ''',
                    (
                        gap.id, gap.capability, gap.title, gap.severity.value, gap.source,
                        fingerprint, payload, gap.created_at, now, gap.status,
                    ),
                )
            conn.commit()

    def detect(
        self,
        *,
        mission_limit: int = 100,
        audit_limit: int = 1000,
        persist: bool = True,
        evaluation_snapshot: EvaluationSnapshot | None = None,
    ) -> list[CapabilityGap]:
        snapshot = evaluation_snapshot or self.evaluation.evaluate(
            mission_limit=mission_limit,
            audit_limit=audit_limit,
            persist=True,
        )
        gaps = []
        gaps.extend(self._registry_gaps())
        gaps.extend(self._metric_gaps(snapshot))
        gaps.extend(self._repeated_tool_failure_gaps(audit_limit))
        gaps.extend(self._failed_mission_gaps(mission_limit))

        deduped: dict[str, CapabilityGap] = {}
        for gap in gaps:
            deduped[self._fingerprint(gap)] = gap
        output = sorted(
            deduped.values(),
            key=lambda gap: (
                {GapSeverity.CRITICAL: 0, GapSeverity.HIGH: 1, GapSeverity.MEDIUM: 2, GapSeverity.LOW: 3}[gap.severity],
                gap.capability.lower(),
                gap.title.lower(),
            ),
        )
        if persist:
            self.persist(output)
        return output

    def list_open(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                '''SELECT gap_json, severity, updated_at FROM v75_capability_gaps
                   WHERE status='OPEN'
                   ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                            updated_at DESC LIMIT ?''',
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            try:
                item = json.loads(row['gap_json'])
                item['updated_at'] = row['updated_at']
                output.append(item)
            except Exception:
                continue
        return output
