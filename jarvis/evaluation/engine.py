from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from uuid import uuid4

from ..agent.mission import MissionStatus
from ..agent.mission_store import MissionStore
from ..capability_registry import CapabilityRegistry
from ..config import settings
from ..security.audit import AuditStore
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EvaluationMetric:
    name: str
    value: float | None
    numerator: int | None = None
    denominator: int | None = None
    unit: str = 'ratio'
    detail: str = ''

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationSnapshot:
    id: str
    created_at: str
    mission_window: int
    audit_window: int
    metrics: dict[str, EvaluationMetric]
    recommendations: tuple[str, ...]
    capability_status: tuple[dict, ...]

    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'mission_window': self.mission_window,
            'audit_window': self.audit_window,
            'metrics': {name: metric.as_dict() for name, metric in self.metrics.items()},
            'recommendations': list(self.recommendations),
            'capability_status': list(self.capability_status),
        }


def _ratio(name: str, numerator: int, denominator: int, detail: str = '') -> EvaluationMetric:
    value = (numerator / denominator) if denominator else None
    return EvaluationMetric(name, value, numerator, denominator, 'ratio', detail)


def _not_measured(name: str, detail: str) -> EvaluationMetric:
    return EvaluationMetric(name, None, None, None, 'ratio', detail)


class SelfEvaluationEngine:
    """Measures JARVIS from persisted evidence instead of model self-claims.

    This engine deliberately returns ``None`` for metrics that current persisted data
    cannot support. Later evaluation/benchmark phases can feed those measurements
    without changing the historical storage format.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        mission_store: MissionStore | None = None,
        audit_store: AuditStore | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.missions = mission_store or MissionStore(self.db_path)
        self.audit = audit_store or AuditStore(self.db_path)
        self.capabilities = capability_registry or CapabilityRegistry()
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_evaluation_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                mission_window INTEGER NOT NULL,
                audit_window INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_eval_time ON v75_evaluation_runs(created_at)')
            conn.commit()

    @staticmethod
    def _terminal_missions(missions: list) -> list:
        return [
            item for item in missions
            if item.status in {
                MissionStatus.COMPLETED,
                MissionStatus.PARTIAL,
                MissionStatus.FAILED,
                MissionStatus.CANCELLED,
            }
        ]

    @staticmethod
    def _tool_rows(rows: list[dict], names: set[str]) -> list[dict]:
        return [row for row in rows if str(row.get('tool_name', '')) in names]

    @staticmethod
    def _execution_metric(name: str, rows: list[dict], detail: str) -> EvaluationMetric:
        measurable = [
            row for row in rows
            if row.get('execution_status') in {
                'SUCCESS', 'PARTIAL', 'FAILED', 'TIMEOUT', 'CANCELLED', 'UNVERIFIED',
            }
        ]
        successes = sum(1 for row in measurable if row.get('execution_status') == 'SUCCESS')
        return _ratio(name, successes, len(measurable), detail)

    def evaluate(self, *, mission_limit: int = 100, audit_limit: int = 1000, persist: bool = True) -> EvaluationSnapshot:
        mission_limit = max(1, min(int(mission_limit), 500))
        audit_limit = max(1, min(int(audit_limit), 5000))

        mission_rows = self.missions.list_recent(mission_limit)
        missions = [self.missions.get(row['id']) for row in mission_rows]
        missions = [item for item in missions if item is not None]
        terminal = self._terminal_missions(missions)

        completed = sum(1 for item in terminal if item.status == MissionStatus.COMPLETED)
        unsuccessful = sum(1 for item in terminal if item.status != MissionStatus.COMPLETED)
        mission_success = _ratio(
            'mission_success_rate', completed, completed + unsuccessful,
            'Completed missions divided by all terminal outcomes; partial, failed, and cancelled missions are not successes.',
        )

        final_verifications = [item.final_verification for item in terminal if item.final_verification is not None]
        verified = sum(1 for item in final_verifications if item.verified)
        verification_success = _ratio(
            'verification_success_rate', verified, len(final_verifications),
            'Fully verified terminal missions divided by terminal missions with final verification evidence.',
        )

        recovery_attempted = [item for item in terminal if item.recovery_count > 0 or item.retry_count > 0]
        recovery_completed = sum(1 for item in recovery_attempted if item.status == MissionStatus.COMPLETED)
        recovery_success = _ratio(
            'recovery_success_rate', recovery_completed, len(recovery_attempted),
            'Missions that completed after retry/recovery activity divided by missions with such activity.',
        )

        replan_attempted = []
        for item in terminal:
            events = self.missions.events(item.id, 2000)
            if any(event.get('event_type') == 'mission.replanned' for event in events):
                replan_attempted.append(item)
        replan_completed = sum(1 for item in replan_attempted if item.status == MissionStatus.COMPLETED)
        replanning_success = _ratio(
            'replanning_success_rate', replan_completed, len(replan_attempted),
            'Completed missions after at least one persisted mission.replanned event.',
        )

        audit_rows = self.audit.list_entries(limit=audit_limit)
        executable = [
            row for row in audit_rows
            if row.get('execution_status') in {
                'SUCCESS', 'PARTIAL', 'FAILED', 'TIMEOUT', 'CANCELLED', 'UNVERIFIED',
            }
        ]
        tool_success = self._execution_metric(
            'tool_success_rate', audit_rows,
            'Successful tool executions divided by SUCCESS + FAILED executions; permission denials are tracked separately.',
        )
        tool_failures = sum(
            1 for row in executable
            if row.get('execution_status') in {'FAILED', 'TIMEOUT', 'CANCELLED'}
        )
        error_rate = _ratio(
            'tool_error_rate', tool_failures, len(executable),
            'Failed, timed-out, or cancelled tool executions divided by all non-denied execution outcomes.',
        )

        denied = sum(1 for row in audit_rows if row.get('execution_status') == 'DENIED')
        permission_denial = _ratio(
            'permission_denial_rate', denied, len(audit_rows),
            'Denied tool calls divided by sampled audit events. This is not automatically a defect.',
        )

        safety_blocks = sum(1 for row in audit_rows if row.get('approval_status') == 'BLOCKED_SECRET')
        safety_block_metric = EvaluationMetric(
            'safety_blocks', float(safety_blocks), safety_blocks, len(audit_rows), 'count',
            'Count of sampled actions blocked by secret-protection checks.',
        )

        latencies = [float(row['latency_ms']) for row in audit_rows if row.get('latency_ms') is not None]
        average_latency = EvaluationMetric(
            'average_tool_latency_ms', mean(latencies) if latencies else None,
            len(latencies), len(audit_rows), 'ms',
            'Mean latency of audit rows that recorded tool execution latency.',
        )

        browser_rows = self._tool_rows(audit_rows, {'open_url', 'browser_search', 'read_web_page', 'search_web', 'search_news'})
        browser_success = self._execution_metric(
            'browser_success_rate', browser_rows,
            'Execution success for persisted browser/web tool events.',
        )

        computer_rows = self._tool_rows(audit_rows, {
            'open_app', 'open_local_path', 'type_text', 'press_key', 'hotkey', 'click_screen',
        })
        computer_success = self._execution_metric(
            'computer_use_success_rate', computer_rows,
            'Execution success for persisted local desktop-control tool events.',
        )

        verification_rows = [row for row in audit_rows if str(row.get('verification_result') or '').strip()]
        verified_tool_rows = sum(
            1 for row in verification_rows
            if str(row.get('verification_result', '')).upper().startswith('VERIFIED')
        )
        ui_verification = _ratio(
            'tool_verification_success_rate', verified_tool_rows, len(verification_rows),
            'Verified persisted tool evidence divided by audit rows that have an explicit verification result.',
        )

        metrics = {
            item.name: item for item in (
                mission_success,
                tool_success,
                verification_success,
                recovery_success,
                replanning_success,
                browser_success,
                computer_success,
                ui_verification,
                average_latency,
                error_rate,
                permission_denial,
                safety_block_metric,
                _not_measured('memory_retrieval_accuracy', 'Requires benchmark relevance labels; runtime search success alone is not accuracy.'),
                _not_measured('ui_targeting_accuracy', 'Requires labelled UI-target benchmark scenarios; no fake estimate is produced.'),
                _not_measured('fallback_rate', 'Provider fallback events are not yet persisted as a normalized metric.'),
                _not_measured('permission_accuracy', 'Needs labelled expected-policy evaluation cases.'),
                _not_measured('safety_violation_rate', 'Needs adversarial benchmark outcomes; blocked actions are tracked separately.'),
                _not_measured('test_pass_rate', 'CI benchmark ingestion is a later evaluation phase.'),
            )
        }

        recommendations: list[str] = []
        thresholds = {
            'mission_success_rate': 0.90,
            'tool_success_rate': 0.95,
            'verification_success_rate': 0.90,
            'recovery_success_rate': 0.80,
            'replanning_success_rate': 0.80,
            'browser_success_rate': 0.90,
            'computer_use_success_rate': 0.90,
        }
        for name, threshold in thresholds.items():
            metric = metrics[name]
            if metric.value is not None and metric.denominator and metric.value < threshold:
                recommendations.append(
                    f'Improve {name.replace("_", " ")}: measured {metric.value:.1%}, target >= {threshold:.0%}.'
                )
        if not recommendations:
            recommendations.append('No threshold-based regression recommendation from currently measurable evidence.')

        snapshot = EvaluationSnapshot(
            id=f'EVAL-{uuid4().hex[:10].upper()}',
            created_at=_now(),
            mission_window=len(missions),
            audit_window=len(audit_rows),
            metrics=metrics,
            recommendations=tuple(recommendations),
            capability_status=tuple(self.capabilities.snapshot()),
        )
        if persist:
            self.save(snapshot)
        return snapshot

    def save(self, snapshot: EvaluationSnapshot) -> None:
        payload = json.dumps(snapshot.as_dict(), ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO v75_evaluation_runs(
                    id, created_at, mission_window, audit_window, snapshot_json
                ) VALUES (?, ?, ?, ?, ?)''',
                (snapshot.id, snapshot.created_at, snapshot.mission_window, snapshot.audit_window, payload),
            )
            conn.commit()

    def history(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT snapshot_json FROM v75_evaluation_runs ORDER BY created_at DESC LIMIT ?',
                (limit,),
            ).fetchall()
        output: list[dict] = []
        for row in rows:
            try:
                output.append(json.loads(row['snapshot_json']))
            except Exception:
                continue
        return output
