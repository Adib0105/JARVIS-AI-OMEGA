"""Central redaction without config/logging dependencies; apply before persistence."""
import re
from typing import Any

_SECRET_KEY_RE = re.compile(
    r'(?i)(api[_-]?key|authorization|password|passwd|secret|token|refresh[_-]?token|access[_-]?token|cookie|credential)'
)
_SECRET_VALUE_PATTERNS = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{4,}\b'),
    re.compile(r'\bsk-or-v1-[A-Za-z0-9_-]{4,}\b'),
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{4,}'),
]


def redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_VALUE_PATTERNS:
        if 'bearer' in pattern.pattern.lower():
            text = pattern.sub(r'\1[REDACTED]', text)
        else:
            text = pattern.sub('[REDACTED]', text)
    text = re.sub(
        r'(?i)\b(api[_-]?key|password|passwd|secret|token|refresh[_-]?token|access[_-]?token|cookie|credential)\s*[:=]\s*[^\s,;]+',
        lambda match: f'{match.group(1)}=[REDACTED]',
        text,
    )
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                clean[str(key)] = '[REDACTED]'
            else:
                clean[str(key)] = redact_value(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
