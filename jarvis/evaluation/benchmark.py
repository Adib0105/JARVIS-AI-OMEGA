from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    category: str
    success: bool
    latency_ms: float
    detail: str = ''

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkSnapshot:
    id: str
    created_at: str
    label: str
    results: tuple[ScenarioResult, ...]
    metrics: dict[str, float | None]

    def as_dict(self) -> dict:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'label': self.label,
            'results': [item.as_dict() for item in self.results],
            'metrics': dict(self.metrics),
        }


class AgentEvaluationBenchmark:
    """Stores objective deterministic scenario results for before/after comparisons."""

    CATEGORY_METRICS = {
        'task': 'task_success_rate',
        'tool': 'tool_accuracy',
        'verification': 'verification_accuracy',
        'recovery': 'recovery_rate',
        'replanning': 'replanning_rate',
        'safety': 'safety_pass_rate',
        'memory': 'memory_accuracy',
        'computer_use': 'computer_use_accuracy',
        'browser': 'browser_accuracy',
    }

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_benchmark_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                label TEXT NOT NULL,
                snapshot_json TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_bench_time ON v75_benchmark_runs(created_at)')
            conn.commit()

    @staticmethod
    def run_case(name: str, category: str, fn) -> ScenarioResult:
        started = time.perf_counter()
        try:
            value = fn()
            if isinstance(value, tuple) and len(value) == 2:
                success, detail = bool(value[0]), str(value[1])
            else:
                success, detail = bool(value), ''
        except Exception as exc:
            success, detail = False, f'{type(exc).__name__}: {exc}'
        return ScenarioResult(
            name=name,
            category=category,
            success=success,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            detail=detail[:2000],
        )

    @classmethod
    def metrics_for(cls, results: list[ScenarioResult] | tuple[ScenarioResult, ...]) -> dict[str, float | None]:
        metrics: dict[str, float | None] = {}
        for category, metric_name in cls.CATEGORY_METRICS.items():
            items = [item for item in results if item.category == category]
            metrics[metric_name] = (sum(1 for item in items if item.success) / len(items)) if items else None
        latencies = [item.latency_ms for item in results]
        metrics['average_latency_ms'] = sum(latencies) / len(latencies) if latencies else None
        metrics['scenario_count'] = float(len(results))
        return metrics

    def record(self, label: str, results: list[ScenarioResult]) -> BenchmarkSnapshot:
        snapshot = BenchmarkSnapshot(
            id=f'BENCH-{uuid4().hex[:10].upper()}',
            created_at=_now(),
            label=str(label)[:160],
            results=tuple(results),
            metrics=self.metrics_for(results),
        )
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO v75_benchmark_runs(id, created_at, label, snapshot_json) VALUES (?, ?, ?, ?)',
                (snapshot.id, snapshot.created_at, snapshot.label, json.dumps(snapshot.as_dict(), ensure_ascii=False, default=str)),
            )
            conn.commit()
        return snapshot

    def history(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT snapshot_json FROM v75_benchmark_runs ORDER BY created_at DESC LIMIT ?', (limit,)
            ).fetchall()
        return [json.loads(row['snapshot_json']) for row in rows]

    @staticmethod
    def compare(before: dict, after: dict) -> dict:
        before_metrics = before.get('metrics') or {}
        after_metrics = after.get('metrics') or {}
        deltas = {}
        regressions = []
        improvements = []
        for key in sorted(set(before_metrics) & set(after_metrics)):
            old = before_metrics.get(key); new = after_metrics.get(key)
            if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
                continue
            delta = float(new) - float(old)
            # latency is lower-is-better; success/accuracy metrics are higher-is-better.
            normalized = -delta if key == 'average_latency_ms' else delta
            deltas[key] = delta
            if normalized < -1e-9:
                regressions.append(key)
            elif normalized > 1e-9:
                improvements.append(key)
        return {
            'before_id': before.get('id'),
            'after_id': after.get('id'),
            'deltas': deltas,
            'improvements': improvements,
            'regressions': regressions,
            'successful_improvement': bool(improvements and not regressions),
        }
