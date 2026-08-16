from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    description: str


_PATTERNS: tuple[tuple[str, re.Pattern, str], ...] = (
    ('openai_key', re.compile(r'\bsk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}\b'), 'API-key-like value'),
    ('bearer_token', re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}'), 'Bearer token'),
    ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), 'Private key block'),
    ('password_assignment', re.compile(r'(?i)\b(?:password|passwd|passcode|pin)\s*[:=]\s*\S{4,}'), 'Password/passcode assignment'),
    ('token_assignment', re.compile(r'(?i)\b(?:access[_ -]?token|refresh[_ -]?token|oauth[_ -]?token|api[_ -]?key|secret)\s*[:=]\s*\S{8,}'), 'Token/secret assignment'),
    ('recovery_code', re.compile(r'(?i)\b(?:recovery|backup)\s+code\s*[:=]\s*[A-Za-z0-9 -]{6,}'), 'Recovery/backup code'),
)


def detect_secrets(text: str) -> list[SecretFinding]:
    value = str(text or '')
    findings = []
    for kind, pattern, description in _PATTERNS:
        if pattern.search(value):
            findings.append(SecretFinding(kind, description))
    return findings


def contains_secret(text: str) -> bool:
    return bool(detect_secrets(text))


def ensure_safe_for_persistent_memory(text: str) -> None:
    findings = detect_secrets(text)
    if findings:
        names = ', '.join(sorted({item.description for item in findings}))
        raise PermissionError(
            f'Refusing to store secret-like content in persistent JARVIS memory ({names}). '
            'Keep passwords, API keys, OAuth tokens and recovery codes out of notes/memory.'
        )
