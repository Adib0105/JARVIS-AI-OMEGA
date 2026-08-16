from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import settings
from ..logging_utils import redact_text, redact_value
from ..storage.sqlite_utils import connect_sqlite
from ..system_tools import system_metrics


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_USAGE_SECRET_KEYS = {
    'api_key', 'apikey', 'authorization', 'password', 'passwd', 'secret',
    'access_token', 'refresh_token', 'id_token', 'oauth_token', 'bearer_token',
    # A singular token value may be a credential. Plural *_tokens fields below are
    # usage counters and are intentionally preserved.
    'token',
}


def _sanitize_usage(value: Any, *, key: str = '') -> Any:
    """Redact credentials while preserving harmless token-count telemetry.

    The generic log redactor intentionally treats any key containing "token" as
    sensitive. Provider usage objects also use names such as `total_tokens`, which
    are numeric counters rather than credentials. Observability needs a narrower
    sanitizer so those counters remain measurable without exposing secrets.
    """
    key_lower = str(key).strip().lower()
    if key_lower in _USAGE_SECRET_KEYS or key_lower.endswith('_api_key'):
        return '[REDACTED]'
    if isinstance(value, dict):
        return {str(k): _sanitize_usage(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_usage(item, key=key) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _explicit_provider_cost(usage: dict | None) -> tuple[float | None, str | None]:
    """Return only an explicit provider-reported cost; never infer pricing."""
    if not isinstance(usage, dict):
        return None, None
    candidates = [
        ('cost', usage.get('cost')),
        ('total_cost', usage.get('total_cost')),
    ]
    details = usage.get('cost_details')
    if isinstance(details, dict):
        candidates.extend([
            ('cost_details.total_cost', details.get('total_cost')),
            ('cost_details.cost', details.get('cost')),
        ])
    for source, value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and float(value) >= 0:
            return float(value), f'provider-reported:{source}'
    return None, None


@dataclass(frozen=True)
class ObservabilityEvent:
    id: str
    timestamp: str
    category: str
    event_type: str
    status: str
    session_id: str | None = None
    mission_id: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
    cost: float | None = None
    cost_source: str | None = None
    usage: dict | None = None
    metadata: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class ObservabilityManager:
    """Structured local telemetry for JARVIS V7.5.

    No raw prompts, passwords, API keys, OAuth tokens or tool arguments are stored.
    Cost remains N/A unless the configured provider explicitly reports a numeric cost.
    """

    ALLOWED_CATEGORIES = {
        'INFO', 'WARNING', 'ERROR', 'SECURITY', 'AUDIT', 'MISSION', 'TOOL',
        'MODEL', 'SELF_DEVELOPMENT', 'MEMORY', 'SYSTEM',
    }

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_observability_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                session_id TEXT,
                mission_id TEXT,
                provider TEXT,
                model TEXT,
                latency_ms REAL,
                cost REAL,
                cost_source TEXT,
                usage_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_obs_time ON v75_observability_events(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_obs_type ON v75_observability_events(category, event_type, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v75_obs_mission ON v75_observability_events(mission_id, timestamp)')
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_resource_samples (
                timestamp TEXT PRIMARY KEY,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                battery_percent REAL,
                network_sent_mb REAL,
                network_received_mb REAL,
                metrics_json TEXT NOT NULL
            )''')
            conn.commit()

    def record(
        self,
        *,
        category: str,
        event_type: str,
        status: str,
        session_id: str | None = None,
        mission_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        latency_ms: float | None = None,
        usage: dict | None = None,
        metadata: dict | None = None,
    ) -> ObservabilityEvent:
        category = str(category).upper().strip()
        if category not in self.ALLOWED_CATEGORIES:
            category = 'INFO'
        safe_usage = _sanitize_usage(usage or {})
        safe_meta = redact_value(metadata or {})
        cost, cost_source = _explicit_provider_cost(safe_usage if isinstance(safe_usage, dict) else {})
        event = ObservabilityEvent(
            id=f'OBS-{uuid4().hex[:12].upper()}',
            timestamp=_now(),
            category=category,
            event_type=redact_text(str(event_type))[:160],
            status=redact_text(str(status).upper())[:80],
            session_id=redact_text(session_id or '')[:120] or None,
            mission_id=redact_text(mission_id or '')[:120] or None,
            provider=redact_text(provider or '')[:120] or None,
            model=redact_text(model or '')[:240] or None,
            latency_ms=float(latency_ms) if isinstance(latency_ms, (int, float)) else None,
            cost=cost,
            cost_source=cost_source,
            usage=safe_usage if isinstance(safe_usage, dict) else {},
            metadata=safe_meta if isinstance(safe_meta, dict) else {},
        )
        with self._connect() as conn:
            conn.execute(
                '''INSERT INTO v75_observability_events(
                    id, timestamp, category, event_type, status, session_id, mission_id,
                    provider, model, latency_ms, cost, cost_source, usage_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    event.id, event.timestamp, event.category, event.event_type, event.status,
                    event.session_id, event.mission_id, event.provider, event.model,
                    event.latency_ms, event.cost, event.cost_source,
                    json.dumps(event.usage or {}, ensure_ascii=False, default=str),
                    json.dumps(event.metadata or {}, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
        return event

    def record_model_turn(
        self,
        *,
        event_type: str,
        status: str,
        session_id: str | None,
        mission_id: str | None,
        provider: str | None,
        model: str | None,
        latency_ms: float | None,
        usage: dict | None,
        fallback: bool = False,
        route: str | None = None,
        error_category: str | None = None,
    ) -> ObservabilityEvent:
        return self.record(
            category='MODEL',
            event_type=event_type,
            status=status,
            session_id=session_id,
            mission_id=mission_id,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            usage=usage,
            metadata={
                'fallback': bool(fallback),
                'route': route or '',
                'error_category': error_category or '',
            },
        )

    def sample_resources(self) -> dict:
        metrics = system_metrics()
        timestamp = _now()
        with self._connect() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO v75_resource_samples(
                    timestamp, cpu_percent, memory_percent, disk_percent, battery_percent,
                    network_sent_mb, network_received_mb, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    timestamp,
                    metrics.get('cpu_percent'), metrics.get('memory_percent'), metrics.get('disk_percent'),
                    metrics.get('battery_percent'), metrics.get('network_sent_mb'), metrics.get('network_received_mb'),
                    json.dumps(redact_value(metrics), ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
        return {'timestamp': timestamp, **metrics}

    def events(
        self,
        *,
        limit: int = 200,
        category: str | None = None,
        event_type: str | None = None,
        mission_id: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if category:
            clauses.append('category=?')
            params.append(str(category).upper())
        if event_type:
            clauses.append('event_type=?')
            params.append(str(event_type))
        if mission_id:
            clauses.append('mission_id=?')
            params.append(str(mission_id))
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        params.append(max(1, min(int(limit), 2000)))
        with self._connect() as conn:
            rows = conn.execute(
                f'''SELECT * FROM v75_observability_events{where}
                    ORDER BY timestamp DESC LIMIT ?''', tuple(params)
            ).fetchall()
        output: list[dict] = []
        for row in rows:
            item = dict(row)
            for key in ('usage_json', 'metadata_json'):
                try:
                    item[key[:-5]] = json.loads(item.pop(key))
                except Exception:
                    item[key[:-5]] = {}
                    item.pop(key, None)
            output.append(item)
        return output

    @staticmethod
    def _since(period: str) -> datetime:
        now = datetime.now(timezone.utc)
        period = period.strip().lower()
        if period == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == 'week':
            return now - timedelta(days=7)
        if period == 'month':
            return now - timedelta(days=30)
        raise ValueError("period must be 'today', 'week', or 'month'")

    def usage_summary(self, period: str = 'today', *, mission_id: str | None = None) -> dict:
        since = self._since(period).isoformat()
        clauses = ["timestamp>=?", "category='MODEL'"]
        params: list[Any] = [since]
        if mission_id:
            clauses.append('mission_id=?')
            params.append(str(mission_id))
        where = ' AND '.join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f'''SELECT provider, model, latency_ms, cost, cost_source, usage_json, metadata_json, status
                    FROM v75_observability_events WHERE {where} ORDER BY timestamp DESC''', tuple(params)
            ).fetchall()
        model_counts: dict[str, int] = {}
        provider_counts: dict[str, int] = {}
        latencies: list[float] = []
        reported_costs: list[float] = []
        fallback_count = 0
        failures = 0
        usage_totals: dict[str, float] = {}
        for row in rows:
            provider = str(row['provider'] or 'unknown')
            model = str(row['model'] or 'unknown')
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            model_counts[model] = model_counts.get(model, 0) + 1
            if row['latency_ms'] is not None:
                latencies.append(float(row['latency_ms']))
            if row['cost'] is not None:
                reported_costs.append(float(row['cost']))
            if str(row['status']).upper() not in {'SUCCESS', 'OK'}:
                failures += 1
            try:
                meta = json.loads(row['metadata_json'] or '{}')
                if meta.get('fallback'):
                    fallback_count += 1
            except Exception:
                pass
            try:
                usage = json.loads(row['usage_json'] or '{}')
            except Exception:
                usage = {}
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens'):
                value = usage.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    usage_totals[key] = usage_totals.get(key, 0.0) + float(value)
        return {
            'period': period,
            'mission_id': mission_id,
            'requests': len(rows),
            'failures': failures,
            'fallbacks': fallback_count,
            'average_latency_ms': round(sum(latencies) / len(latencies), 3) if latencies else None,
            'provider_usage': provider_counts,
            'model_usage': model_counts,
            'token_usage': usage_totals,
            'reported_cost': round(sum(reported_costs), 10) if reported_costs else None,
            'cost_source': 'provider-reported only' if reported_costs else 'N/A — provider did not report explicit cost',
        }

    def dashboard_snapshot(self) -> dict:
        return {
            'resources': self.sample_resources(),
            'today': self.usage_summary('today'),
            'week': self.usage_summary('week'),
            'month': self.usage_summary('month'),
            'recent_events': self.events(limit=30),
        }
