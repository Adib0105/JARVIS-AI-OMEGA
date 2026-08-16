from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..logging_utils import redact_text, redact_value
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def arguments_hash(args: dict) -> str:
    """Hash sanitized arguments without persisting their raw values."""
    sanitized = redact_value(args)
    payload = json.dumps(sanitized, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


class AuditStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v7_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                mission_id TEXT,
                session_id TEXT,
                request_summary TEXT,
                tool_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                arguments_hash TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                error_type TEXT,
                latency_ms REAL,
                provider TEXT,
                model TEXT,
                verification_result TEXT
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_audit_time ON v7_audit_log(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_audit_mission ON v7_audit_log(mission_id, id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_v7_audit_tool ON v7_audit_log(tool_name, id)')
            conn.commit()

    def record(
        self,
        *,
        mission_id: str | None,
        session_id: str | None,
        request_summary: str | None,
        tool_name: str,
        risk_level: str,
        capabilities: list[str],
        args: dict,
        approval_status: str,
        execution_status: str,
        error_type: str | None = None,
        latency_ms: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        verification_result: str | None = None,
    ) -> int:
        safe_request = redact_text(request_summary or '')[:800]
        safe_provider = redact_text(provider or '')[:120]
        safe_model = redact_text(model or '')[:240]
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                '''INSERT INTO v7_audit_log(
                    timestamp, mission_id, session_id, request_summary, tool_name, risk_level,
                    capabilities_json, arguments_hash, approval_status, execution_status,
                    error_type, latency_ms, provider, model, verification_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    _now(), mission_id, session_id, safe_request, tool_name, risk_level,
                    json.dumps(capabilities, ensure_ascii=False), arguments_hash(args), approval_status,
                    execution_status, error_type, latency_ms, safe_provider, safe_model,
                    verification_result,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_verification(self, audit_id: int, result: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                'UPDATE v7_audit_log SET verification_result=? WHERE id=?',
                (redact_text(result)[:500], int(audit_id)),
            )
            conn.commit()

    def list_entries(
        self,
        *,
        limit: int = 200,
        mission_id: str | None = None,
        tool_name: str | None = None,
        execution_status: str | None = None,
        high_risk_only: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if mission_id:
            clauses.append('mission_id=?')
            params.append(mission_id)
        if tool_name:
            clauses.append('tool_name=?')
            params.append(tool_name)
        if execution_status:
            clauses.append('execution_status=?')
            params.append(execution_status)
        if high_risk_only:
            clauses.append("risk_level IN ('HIGH', 'CRITICAL')")
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        params.append(max(1, min(int(limit), 1000)))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f'''SELECT id, timestamp, mission_id, session_id, request_summary, tool_name,
                           risk_level, capabilities_json, arguments_hash, approval_status,
                           execution_status, error_type, latency_ms, provider, model,
                           verification_result
                    FROM v7_audit_log{where} ORDER BY id DESC LIMIT ?''',
                tuple(params),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            try:
                item['capabilities'] = json.loads(item.pop('capabilities_json'))
            except Exception:
                item['capabilities'] = []
                item.pop('capabilities_json', None)
            output.append(item)
        return output
