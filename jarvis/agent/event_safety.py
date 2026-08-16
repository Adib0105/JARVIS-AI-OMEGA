from __future__ import annotations

import hashlib
import json
from typing import Any

from ..logging_utils import redact_text, redact_value

# Tool arguments that may contain private/free-form user or document data. Persist
# only shape/length information for these fields; verification may still use safe
# cryptographic hints rather than the original content.
_PRIVATE_ARGUMENT_KEYS = {
    'content', 'text', 'body', 'prompt', 'messages', 'message', 'query_text',
    'password', 'passwd', 'secret', 'token', 'api_key', 'authorization',
    'refresh_token', 'access_token',
}

_PRIVATE_RESULT_KEYS = {
    'content', 'text', 'body', 'messages', 'message', 'raw', 'transcript',
    'html', 'markdown', 'document_text', 'page_content',
}

_SAFE_RESULT_KEYS = {
    'ok', 'id', 'message_id', 'event_id', 'path', 'name', 'status', 'returncode',
    'count', 'characters', 'size', 'size_bytes', 'chunks', 'content_hash',
    'duplicate_unchanged', 'verified', 'verification', 'error', 'reason',
    'backend', 'confidence', 'action', 'provider', 'model', 'latency_ms',
}


def _sha256(value: Any) -> str:
    payload = json.dumps(
        redact_value(value), sort_keys=True, ensure_ascii=False, default=str
    ).encode('utf-8', errors='replace')
    return hashlib.sha256(payload).hexdigest()


def _string_summary(value: str, *, private: bool = False, max_chars: int = 240) -> str:
    safe = redact_text(value)
    if private:
        digest = hashlib.sha256(value.encode('utf-8', errors='replace')).hexdigest()[:16]
        return f'[PRIVATE_TEXT:{len(value)} chars; sha256={digest}]'
    if len(safe) <= max_chars:
        return safe
    return safe[:max_chars] + f'… [{len(safe)} chars]'


def summarize_arguments(args: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in dict(args or {}).items():
        lower = str(key).lower()
        private = lower in _PRIVATE_ARGUMENT_KEYS or any(
            marker in lower for marker in ('password', 'secret', 'token', 'api_key', 'authorization')
        )
        if isinstance(value, str):
            output[str(key)] = _string_summary(value, private=private)
        elif private:
            output[str(key)] = f'[PRIVATE_VALUE:{type(value).__name__}]'
        elif isinstance(value, (int, float, bool)) or value is None:
            output[str(key)] = value
        elif isinstance(value, (list, tuple, set)):
            output[str(key)] = {'type': type(value).__name__, 'items': len(value)}
        elif isinstance(value, dict):
            output[str(key)] = {'type': 'dict', 'keys': sorted(map(str, value.keys()))[:30]}
        else:
            output[str(key)] = f'[{type(value).__name__}]'
    return output


def safe_evidence(value: Any, *, depth: int = 0) -> Any:
    """Return verification evidence that is useful but safe to persist.

    Free-form content/body/text fields are summarized instead of copied. Unknown
    nested payloads are bounded so provider/document/browser output cannot silently
    turn the mission database into a private-content archive.
    """
    if depth > 4:
        return '[MAX_DEPTH]'
    if isinstance(value, str):
        return _string_summary(value, max_chars=400)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if len(items) > 20:
            return {
                'type': 'list',
                'items': len(items),
                'sample': [safe_evidence(x, depth=depth + 1) for x in items[:5]],
            }
        return [safe_evidence(x, depth=depth + 1) for x in items]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            lower = key_s.lower()
            if lower in _PRIVATE_RESULT_KEYS or any(
                marker in lower for marker in ('password', 'secret', 'token', 'api_key', 'authorization')
            ):
                if isinstance(item, str):
                    out[key_s] = _string_summary(item, private=True)
                else:
                    out[key_s] = f'[PRIVATE_VALUE:{type(item).__name__}]'
                continue
            if lower in _SAFE_RESULT_KEYS or depth < 2:
                out[key_s] = safe_evidence(item, depth=depth + 1)
        if not out and value:
            out['summary'] = {'type': 'dict', 'keys': sorted(map(str, value.keys()))[:30]}
        return out
    return _string_summary(str(value), max_chars=240)


def sanitize_tool_output(output: Any) -> str:
    try:
        payload = json.loads(output) if isinstance(output, str) else output
    except Exception:
        return json.dumps(
            {'summary': _string_summary(str(output), max_chars=600)},
            ensure_ascii=False,
        )
    return json.dumps(safe_evidence(payload), ensure_ascii=False, default=str)


def sanitize_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    event = dict(event or {})
    args = event.get('args') if isinstance(event.get('args'), dict) else {}
    safe = {
        'name': str(event.get('name', '')),
        'args': summarize_arguments(args),
        'arguments_hash': _sha256(args),
        'output': sanitize_tool_output(event.get('output', '')),
    }
    for key in (
        'risk_level', 'capabilities', 'approval_status', 'audit_id', 'started_at',
        'completed_at', 'latency_ms', 'verification_hints',
    ):
        if key in event:
            safe[key] = safe_evidence(event.get(key))
    return safe


__all__ = [
    'safe_evidence', 'sanitize_tool_event', 'sanitize_tool_output',
    'summarize_arguments',
]
