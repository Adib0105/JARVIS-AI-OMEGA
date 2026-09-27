from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from ..config import settings
from ..errors import classify_exception
from ..memory import MemoryStore
from ..security.audit import AuditStore
from ..security.capabilities import profile_for
from ..security.policy import CapabilityPermissionGate
from ..security.secrets import ensure_safe_for_persistent_memory
from ..tools import ToolRegistry
from .budget import CURRENT
from .effects import EffectLedger
from .event_safety import sanitize_tool_event


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_PERSISTENT_TEXT_TOOLS = {
    'remember_fact': ('fact',),
    'add_note': ('title', 'content'),
    'add_todo': ('title',),
    'add_reminder': ('text',),
}


class RecordingToolRegistry(ToolRegistry):
    """V7 runtime around existing handlers: capability gate + audit + evidence.

    Raw tool input/output exists only during the synchronous handler call. Events
    exposed to missions are privacy-minimized before they are queued, so persisted
    mission state cannot become a shadow archive of email bodies, file contents or
    secrets.
    """

    def __init__(
        self,
        memory: MemoryStore,
        confirmer: Callable[[str, dict], object] | None = None,
        *,
        context_provider: Callable[[], dict] | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        gate = CapabilityPermissionGate(
            confirmer,
            require_approval=settings.require_local_approval,
        )
        # Inject the V7 gate at construction time. ToolRegistry no longer creates a
        # hidden legacy gate only for this subclass to overwrite it afterwards.
        super().__init__(memory, confirmer, permission_checker=gate)
        self.permissions = gate
        self.audit = audit_store or AuditStore()
        self.context_provider = context_provider or (lambda: {})
        self.effects = EffectLedger(memory.db_path)
        self._call_state = threading.local()
        self._events: list[dict] = []
        self._events_lock = threading.RLock()

    @staticmethod
    def _memory_secret_check(name: str, args: dict) -> None:
        fields = _PERSISTENT_TEXT_TOOLS.get(name)
        if not fields:
            return
        text = '\n'.join(str(args.get(field, '')) for field in fields)
        ensure_safe_for_persistent_memory(text)

    @staticmethod
    def _execution_result(output: str) -> tuple[str, str | None]:
        try:
            payload = json.loads(output)
        except Exception:
            return 'FAILED', 'TOOL_ERROR'
        if isinstance(payload, dict) and payload.get('ok') is True:
            return 'SUCCESS', None
        error = str(payload.get('error', 'Tool failed.')) if isinstance(payload, dict) else 'Tool failed.'
        lower = error.lower()
        if 'not approved' in lower or 'permission' in lower or 'denied' in lower or 'cancellation requested' in lower:
            return 'DENIED', 'PERMISSION_ERROR'
        failure = classify_exception(RuntimeError(error), operation='tool')
        return 'FAILED', failure.category.value

    @staticmethod
    def _verification_hints(name: str, args: dict) -> dict:
        # File-write verification can compare hashes instead of storing the written
        # source text in mission history.
        if name == 'write_local_text_file':
            content = str(args.get('content', ''))
            return {
                'content_sha256': hashlib.sha256(
                    content.encode('utf-8', errors='replace')
                ).hexdigest(),
                'content_characters': len(content),
            }
        return {}

    def _before_dispatch(self, name, args):
        super()._before_dispatch(name, args)
        if profile_for(name).side_effecting:
            context = dict(self.context_provider() or {})
            self._call_state.intent = self.effects.begin(name, args, context.get('mission_id'))

    def call(self, name: str, args: dict) -> str:
        if CURRENT.get():
            CURRENT.get().tool()
        started_iso = _now()
        started = time.perf_counter()
        profile = profile_for(name)
        blocked_secret = False
        self._call_state.intent = None
        try:
            context = dict(self.context_provider() or {})
        except Exception:
            context = {}

        try:
            self._memory_secret_check(name, args)
            output = super().call(name, args)
        except PermissionError as exc:
            blocked_secret = True
            output = json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False)
        except Exception as exc:
            output = json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        outcome = self.permissions.consume_last_outcome()
        intent = self._call_state.intent
        execution_status, error_type = self._execution_result(output)
        if intent:
            # FAILED is uncertain once dispatch entered the handler. Permission
            # denial is known not to have executed and can be reconsidered later.
            state = 'ACKNOWLEDGED' if execution_status == 'SUCCESS' else 'DENIED' if outcome is not None and not outcome.allowed else 'UNCERTAIN'
            self.effects.finish(intent, state)

        if blocked_secret:
            approval_status = 'BLOCKED_SECRET'
        elif outcome is None:
            approval_status = 'NOT_RECORDED'
        elif outcome.allowed and outcome.reason.startswith('Allowed by'):
            approval_status = 'AUTO_ALLOWED'
        else:
            approval_status = outcome.decision.value.upper()

        try:
            context = dict(self.context_provider() or {})
        except Exception:
            context = {}
        audit_id = self.audit.record(
            mission_id=context.get('mission_id'),
            session_id=context.get('session_id'),
            request_summary=context.get('request_summary'),
            tool_name=name,
            risk_level=profile.risk.value,
            capabilities=[item.value for item in sorted(profile.capabilities, key=lambda item: item.value)],
            args=args,
            approval_status=approval_status,
            execution_status=execution_status,
            error_type=error_type,
            latency_ms=elapsed_ms,
            provider=context.get('provider'),
            model=context.get('model'),
        )

        raw_event = {
            'name': name,
            'intent_id': intent,
            'args': dict(args),
            'output': output,
            'risk_level': profile.risk.value,
            'capabilities': [item.value for item in sorted(profile.capabilities, key=lambda item: item.value)],
            'approval_status': approval_status,
            'audit_id': audit_id,
            'started_at': started_iso,
            'completed_at': _now(),
            'latency_ms': elapsed_ms,
            'verification_hints': self._verification_hints(name, args),
        }
        event = sanitize_tool_event(raw_event)
        with self._events_lock:
            self._events.append(event)
        return output

    def clear_events(self) -> None:
        with self._events_lock:
            self._events.clear()

    def drain_events(self) -> list[dict]:
        with self._events_lock:
            events = list(self._events)
            self._events.clear()
        return events

    def snapshot_events(self) -> list[dict]:
        with self._events_lock:
            return list(self._events)
