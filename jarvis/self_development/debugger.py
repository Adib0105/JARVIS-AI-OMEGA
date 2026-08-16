from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DebugDiagnosis:
    category: str
    summary: str
    repair_focus: tuple[str, ...]
    attempt: int
    can_retry: bool

    def as_dict(self) -> dict:
        return {
            'category': self.category,
            'summary': self.summary,
            'repair_focus': list(self.repair_focus),
            'attempt': self.attempt,
            'can_retry': self.can_retry,
        }


class SelfDebugger:
    CATEGORIES = (
        ('SYNTAX', ('syntaxerror', 'indentationerror')),
        ('IMPORT', ('modulenotfounderror', 'importerror', 'cannot import name')),
        ('DEPENDENCY', ('no matching distribution', 'dependency', 'package not found')),
        ('DATABASE', ('sqlite', 'database is locked', 'operationalerror')),
        ('PERMISSION', ('permissionerror', 'access is denied', 'not approved')),
        ('CONCURRENCY', ('deadlock', 'thread', 'race condition', 'winerror 32')),
        ('API', ('rate limit', 'unauthorized', 'api', 'http 4', 'http 5')),
        ('PLATFORM', ('winerror', 'linux', 'darwin', 'platform')),
        ('LOGIC', ('assertionerror', 'failed (failures=', 'test failed')),
    )

    def __init__(self) -> None:
        self.max_attempts = max(0, min(int(os.getenv('MAX_SELF_REPAIR_ATTEMPTS', '3')), 10))

    def diagnose(self, output: str, *, attempt: int) -> DebugDiagnosis:
        text = str(output)
        lower = text.lower()
        category = 'UNKNOWN'
        for name, tokens in self.CATEGORIES:
            if any(token in lower for token in tokens):
                category = name
                break
        focus = {
            'SYNTAX': ('open the first syntax traceback location', 'repair syntax only', 're-run compileall'),
            'IMPORT': ('inspect the failing import and package boundary', 'avoid silent dependency installation'),
            'DEPENDENCY': ('verify requirements/configuration', 'require explicit dependency review'),
            'DATABASE': ('inspect connection lifetime and transaction boundaries', 'preserve data and migrations'),
            'PERMISSION': ('inspect requested capability and policy', 'do not weaken security to make the test pass'),
            'CONCURRENCY': ('inspect thread/process/file handle lifetime', 'add deterministic cleanup regression test'),
            'API': ('inspect provider adapter/error classification', 'do not hard-code provider responses'),
            'PLATFORM': ('reproduce platform-specific branch', 'preserve cross-platform behavior'),
            'LOGIC': ('inspect the first assertion failure', 'fix root behavior rather than expected test values'),
            'UNKNOWN': ('inspect traceback/logs and relevant source', 'minimize the repair scope'),
        }[category]
        attempt = max(1, int(attempt))
        return DebugDiagnosis(
            category=category,
            summary=f'{category} failure detected from test/build output.',
            repair_focus=focus,
            attempt=attempt,
            can_retry=attempt < self.max_attempts,
        )
