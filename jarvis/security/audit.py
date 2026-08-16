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


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str
    ).encode('utf-8', errors='replace')
    return hashlib.sha256(payload).hexdigest()


def arguments_hash(args: dict) -> str:
    """Hash sanitized arguments without persisting their raw values."""
    return _hash_json(redact_value(args))


class AuditStore:
    """Security audit log with an additive tamper-evident integrity chain.

    Existing pre-chain audit rows are preserved and reported as LEGACY_UNCHAINED.
    New record/verification mutations append hash-chain events in the same SQLite
    transaction. This is tamper evidence, not a substitute for OS/database access
    control: a fully privileged attacker who can rewrite the entire database can
    also rewrite local integrity metadata.
    """

    _ZERO_HASH = '0' * 64
    _IMMUTABLE_FIELDS = (
        'id', 'timestamp', 'mission_id', 'session_id', 'request_summary',
        'tool_name', 'risk_level', 'capabilities_json', 'arguments_hash',
        'approval_status', 'execution_status', 'error_type', 'latency_ms',
        'provider', 'model',
    )

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
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_audit_integrity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_v75_audit_integrity_audit '
                'ON v75_audit_integrity(audit_id, id)'
            )
            conn.commit()

    @classmethod
    def _record_payload_hash(cls, row: dict[str, Any]) -> str:
        return _hash_json({key: row.get(key) for key in cls._IMMUTABLE_FIELDS})

    @staticmethod
    def _verification_payload_hash(audit_id: int, result: str | None) -> str:
        return _hash_json({
            'audit_id': int(audit_id),
            'verification_result': str(result or ''),
        })

    @classmethod
    def _integrity_event_hash(
        cls,
        *,
        prev_hash: str,
        audit_id: int,
        event_type: str,
        payload_hash: str,
    ) -> str:
        return _hash_json({
            'prev_hash': prev_hash,
            'audit_id': int(audit_id),
            'event_type': str(event_type),
            'payload_hash': payload_hash,
        })

    def _append_integrity(
        self,
        conn,
        *,
        audit_id: int,
        event_type: str,
        payload_hash: str,
    ) -> str:
        last = conn.execute(
            'SELECT event_hash FROM v75_audit_integrity ORDER BY id DESC LIMIT 1'
        ).fetchone()
        prev_hash = str(last['event_hash']) if last else self._ZERO_HASH
        event_hash = self._integrity_event_hash(
            prev_hash=prev_hash,
            audit_id=audit_id,
            event_type=event_type,
            payload_hash=payload_hash,
        )
        conn.execute(
            '''INSERT INTO v75_audit_integrity(
                audit_id, event_type, prev_hash, payload_hash, event_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)''',
            (int(audit_id), event_type, prev_hash, payload_hash, event_hash, _now()),
        )
        return event_hash

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
        safe_verification = redact_text(verification_result or '')[:500] if verification_result else None
        with self._lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
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
                    safe_verification,
                ),
            )
            audit_id = int(cursor.lastrowid)
            row = conn.execute(
                '''SELECT id, timestamp, mission_id, session_id, request_summary, tool_name,
                          risk_level, capabilities_json, arguments_hash, approval_status,
                          execution_status, error_type, latency_ms, provider, model
                   FROM v7_audit_log WHERE id=?''',
                (audit_id,),
            ).fetchone()
            self._append_integrity(
                conn,
                audit_id=audit_id,
                event_type='record',
                payload_hash=self._record_payload_hash(dict(row)),
            )
            if safe_verification:
                self._append_integrity(
                    conn,
                    audit_id=audit_id,
                    event_type='verification',
                    payload_hash=self._verification_payload_hash(audit_id, safe_verification),
                )
            conn.commit()
            return audit_id

    def update_verification(self, audit_id: int, result: str) -> None:
        safe_result = redact_text(result)[:500]
        with self._lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cur = conn.execute(
                'UPDATE v7_audit_log SET verification_result=? WHERE id=?',
                (safe_result, int(audit_id)),
            )
            if cur.rowcount:
                self._append_integrity(
                    conn,
                    audit_id=int(audit_id),
                    event_type='verification',
                    payload_hash=self._verification_payload_hash(int(audit_id), safe_result),
                )
            conn.commit()

    def verify_integrity(self) -> dict[str, Any]:
        """Verify hash links plus current audit-row payloads.

        Legacy rows that predate integrity chaining are reported separately and do
        not make the chain fail. Any mutation to a chained immutable audit field or
        to the current verification result is reported as BROKEN.
        """
        with self._lock, self._connect() as conn:
            audit_rows = conn.execute(
                '''SELECT id, timestamp, mission_id, session_id, request_summary, tool_name,
                          risk_level, capabilities_json, arguments_hash, approval_status,
                          execution_status, error_type, latency_ms, provider, model,
                          verification_result
                   FROM v7_audit_log ORDER BY id ASC'''
            ).fetchall()
            chain_rows = conn.execute(
                '''SELECT id, audit_id, event_type, prev_hash, payload_hash, event_hash, created_at
                   FROM v75_audit_integrity ORDER BY id ASC'''
            ).fetchall()

        audits = {int(row['id']): dict(row) for row in audit_rows}
        record_chained = {
            int(row['audit_id']) for row in chain_rows if str(row['event_type']) == 'record'
        }
        legacy_ids = sorted(set(audits) - record_chained)
        last_verification_event: dict[int, int] = {}
        for row in chain_rows:
            if str(row['event_type']) == 'verification':
                last_verification_event[int(row['audit_id'])] = int(row['id'])

        previous = self._ZERO_HASH
        first_bad_event = None
        first_bad_audit = None
        reason = ''
        for row_obj in chain_rows:
            row = dict(row_obj)
            audit_id = int(row['audit_id'])
            event_id = int(row['id'])
            if str(row['prev_hash']) != previous:
                first_bad_event, first_bad_audit = event_id, audit_id
                reason = 'Integrity chain previous-hash link mismatch.'
                break
            expected_event = self._integrity_event_hash(
                prev_hash=previous,
                audit_id=audit_id,
                event_type=str(row['event_type']),
                payload_hash=str(row['payload_hash']),
            )
            if expected_event != str(row['event_hash']):
                first_bad_event, first_bad_audit = event_id, audit_id
                reason = 'Integrity event hash mismatch.'
                break
            audit = audits.get(audit_id)
            if audit is None:
                first_bad_event, first_bad_audit = event_id, audit_id
                reason = 'Integrity event references a missing audit row.'
                break
            if str(row['event_type']) == 'record':
                expected_payload = self._record_payload_hash(audit)
                if expected_payload != str(row['payload_hash']):
                    first_bad_event, first_bad_audit = event_id, audit_id
                    reason = 'Chained audit record payload was modified.'
                    break
            elif (
                str(row['event_type']) == 'verification'
                and last_verification_event.get(audit_id) == event_id
            ):
                expected_payload = self._verification_payload_hash(
                    audit_id, audit.get('verification_result')
                )
                if expected_payload != str(row['payload_hash']):
                    first_bad_event, first_bad_audit = event_id, audit_id
                    reason = 'Current audit verification result was modified.'
                    break
            previous = str(row['event_hash'])

        ok = first_bad_event is None
        if not chain_rows:
            status = 'LEGACY_UNCHAINED' if audits else 'EMPTY'
        elif not ok:
            status = 'BROKEN'
        elif legacy_ids:
            status = 'OK_WITH_LEGACY'
        else:
            status = 'OK'
        return {
            'ok': ok,
            'status': status,
            'audit_rows': len(audits),
            'integrity_events': len(chain_rows),
            'chained_audit_rows': len(record_chained),
            'legacy_unchained_rows': len(legacy_ids),
            'legacy_unchained_ids': legacy_ids[:50],
            'head_hash': previous if chain_rows and ok else None,
            'first_bad_event_id': first_bad_event,
            'first_bad_audit_id': first_bad_audit,
            'reason': reason,
        }

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
