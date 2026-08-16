from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..security.audit import AuditStore
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RepeatedWorkflow:
    id: str
    tools: tuple[str, ...]
    occurrences: int
    sessions: int
    confidence: float
    evidence: tuple[str, ...]
    proposal_text: str
    created_at: str

    def as_dict(self) -> dict:
        data = asdict(self)
        data['tools'] = list(self.tools)
        data['evidence'] = list(self.evidence)
        return data


class WorkflowLearningEngine:
    """Detect repeated successful tool sequences and propose reuse.

    It deliberately has no activation/execution method. Permanent automation is a
    separate user-approved skill/release decision.
    """

    SENSITIVE_TOOLS = {'gmail_send', 'calendar_create', 'write_local_text_file', 'type_text', 'click_screen'}

    def __init__(self, db_path: Path | None = None, *, audit_store: AuditStore | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.audit = audit_store or AuditStore(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_workflow_proposals (
                fingerprint TEXT PRIMARY KEY,
                workflow_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL
            )''')
            conn.commit()

    @staticmethod
    def _fingerprint(sequence: tuple[str, ...]) -> str:
        return hashlib.sha256('|'.join(sequence).encode('utf-8')).hexdigest()

    def detect(self, *, audit_limit: int = 1000, min_occurrences: int = 3, min_length: int = 2, max_length: int = 6, persist: bool = True) -> list[RepeatedWorkflow]:
        rows = list(reversed(self.audit.list_entries(limit=max(1, min(audit_limit, 1000)))))
        sessions: dict[str, list[str]] = {}
        for row in rows:
            session_id = str(row.get('session_id') or '').strip()
            tool = str(row.get('tool_name') or '').strip()
            if not session_id or not tool or row.get('execution_status') != 'SUCCESS':
                continue
            sessions.setdefault(session_id, []).append(tool)

        counts: dict[tuple[str, ...], int] = {}
        session_counts: dict[tuple[str, ...], set[str]] = {}
        min_length = max(2, int(min_length))
        max_length = max(min_length, min(int(max_length), 8))
        for session_id, tools in sessions.items():
            for size in range(min_length, min(max_length, len(tools)) + 1):
                for index in range(0, len(tools) - size + 1):
                    sequence = tuple(tools[index:index + size])
                    # High-risk side effects are not auto-learned into reusable workflows.
                    if any(tool in self.SENSITIVE_TOOLS for tool in sequence):
                        continue
                    counts[sequence] = counts.get(sequence, 0) + 1
                    session_counts.setdefault(sequence, set()).add(session_id)

        output: list[RepeatedWorkflow] = []
        for sequence, occurrences in counts.items():
            if occurrences < max(2, int(min_occurrences)):
                continue
            sessions_seen = len(session_counts.get(sequence, set()))
            # Confidence is evidence density, capped below certainty because semantic
            # equivalence of arguments is intentionally unavailable from redacted audit logs.
            confidence = min(0.95, 0.55 + min(occurrences, 8) * 0.05 + min(sessions_seen, 4) * 0.05)
            readable = ' → '.join(sequence)
            workflow = RepeatedWorkflow(
                id=f'WF-{uuid4().hex[:10].upper()}',
                tools=sequence,
                occurrences=occurrences,
                sessions=sessions_seen,
                confidence=round(confidence, 3),
                evidence=(
                    f'occurrences={occurrences}',
                    f'sessions={sessions_seen}',
                    'argument values are not stored in audit logs, so semantic parameter similarity is unverified',
                ),
                proposal_text=f'Create reusable workflow skill for: {readable}?',
                created_at=_now(),
            )
            output.append(workflow)

        # Prefer longer/higher-evidence workflows and suppress strict sub-sequences
        # when a stronger repeated super-sequence already explains the same pattern.
        output.sort(key=lambda item: (-item.occurrences, -len(item.tools), item.tools))
        filtered: list[RepeatedWorkflow] = []
        for item in output:
            if any(
                item.occurrences == kept.occurrences
                and len(item.tools) < len(kept.tools)
                and any(tuple(kept.tools[i:i + len(item.tools)]) == item.tools for i in range(len(kept.tools) - len(item.tools) + 1))
                for kept in filtered
            ):
                continue
            filtered.append(item)

        if persist:
            self.persist(filtered)
        return filtered

    def persist(self, workflows: list[RepeatedWorkflow]) -> None:
        now = _now()
        with self._connect() as conn:
            for workflow in workflows:
                fingerprint = self._fingerprint(workflow.tools)
                payload = json.dumps(workflow.as_dict(), ensure_ascii=False)
                conn.execute(
                    '''INSERT INTO v75_workflow_proposals(fingerprint, workflow_json, created_at, updated_at, status)
                       VALUES (?, ?, ?, ?, 'PROPOSED')
                       ON CONFLICT(fingerprint) DO UPDATE SET workflow_json=excluded.workflow_json,
                       updated_at=excluded.updated_at''',
                    (fingerprint, payload, workflow.created_at, now),
                )
            conn.commit()

    def recent(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT workflow_json, status, updated_at FROM v75_workflow_proposals ORDER BY updated_at DESC LIMIT ?',
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = json.loads(row['workflow_json'])
            item['status'] = row['status']
            item['updated_at'] = row['updated_at']
            result.append(item)
        return result
