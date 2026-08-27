from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


# Generated/self-authored code may improve normal application code, but it must not
# rewrite the mechanisms that decide what it is allowed to change, how a sandbox is
# created, how tests are judged, how production is activated, or how rollback works.
# These paths form the local self-development control plane. Changing them requires
# a normal human-reviewed engineering change outside the autonomous pipeline.
IMMUTABLE_SECURITY_PREFIXES = (
    'jarvis/security/',
)

IMMUTABLE_SELF_DEVELOPMENT_CONTROL_PATHS = frozenset({
    'jarvis/self_development/policies.py',
    'jarvis/self_development/sandbox.py',
    'jarvis/self_development/builder.py',
    'jarvis/self_development/git_manager.py',
    'jarvis/self_development/lease.py',
    'jarvis/self_development/rollback.py',
    'jarvis/self_development/release.py',
    'jarvis/self_development/engine.py',
    'jarvis/self_development/tester.py',
    'jarvis/skills/activation.py',
})

PROTECTED_PRODUCTION_PREFIXES = (
    '.git/',
    '.env',
    'data/',
    'workspace/production/',
)


@dataclass(frozen=True)
class PolicyCheck:
    allowed: bool
    reasons: tuple[str, ...]
    files_changed: int
    lines_changed: int

    def as_dict(self) -> dict:
        return {
            'allowed': self.allowed,
            'reasons': list(self.reasons),
            'files_changed': self.files_changed,
            'lines_changed': self.lines_changed,
        }


class SelfDevelopmentPolicy:
    """Non-bypassable default policy for generated experiments.

    This policy is an enforcement boundary, not a prompt preference. Generated
    changes cannot edit the security core or the self-development control plane,
    even inside an otherwise isolated worktree.
    """

    def __init__(self) -> None:
        self.max_files_changed = max(1, min(int(os.getenv('MAX_FILES_CHANGED', '20')), 200))
        self.max_lines_changed = max(20, min(int(os.getenv('MAX_LINES_CHANGED', '1200')), 20000))
        self.max_build_time = max(10, min(int(os.getenv('MAX_BUILD_TIME', '300')), 1800))
        self.max_test_time = max(10, min(int(os.getenv('MAX_TEST_TIME', '300')), 1800))
        self.require_approval_for_production = os.getenv(
            'REQUIRE_APPROVAL_FOR_PRODUCTION', 'true'
        ).strip().lower() in {'1', 'true', 'yes', 'on'}

    @staticmethod
    def normalize(path: str | Path) -> str:
        raw = str(path).replace('\\', '/')
        while raw.startswith('./'):
            raw = raw[2:]
        try:
            return str(PurePosixPath(raw))
        except Exception:
            return raw

    def path_allowed(self, path: str | Path) -> tuple[bool, str]:
        value = self.normalize(path)
        lower = value.lower()
        if not value or value == '.':
            return False, 'empty/root path is not a valid generated file'
        if value.startswith('/') or re.match(r'^[a-zA-Z]:/', value):
            return False, 'absolute paths are not allowed'
        if '..' in PurePosixPath(value).parts:
            return False, 'path traversal is not allowed'
        if lower == '.env' or lower.startswith('.env.'):
            return False, 'environment/secret files are protected'
        if any(lower.startswith(prefix.lower()) for prefix in IMMUTABLE_SECURITY_PREFIXES):
            return False, 'immutable security core path'
        if lower in IMMUTABLE_SELF_DEVELOPMENT_CONTROL_PATHS:
            return False, 'immutable self-development control-plane path'
        if any(lower.startswith(prefix.lower()) for prefix in PROTECTED_PRODUCTION_PREFIXES):
            return False, 'protected production/runtime data path'
        return True, ''

    def validate_change_set(self, changed_files: list[str], lines_changed: int) -> PolicyCheck:
        reasons: list[str] = []
        unique = sorted({self.normalize(path) for path in changed_files})
        if len(unique) > self.max_files_changed:
            reasons.append(f'file limit exceeded: {len(unique)} > {self.max_files_changed}')
        if int(lines_changed) > self.max_lines_changed:
            reasons.append(f'line limit exceeded: {lines_changed} > {self.max_lines_changed}')
        for path in unique:
            allowed, reason = self.path_allowed(path)
            if not allowed:
                reasons.append(f'{path}: {reason}')
        return PolicyCheck(not reasons, tuple(reasons), len(unique), int(lines_changed))

    def can_activate_production(self, *, explicit_user_approval: bool) -> bool:
        return bool(explicit_user_approval)
