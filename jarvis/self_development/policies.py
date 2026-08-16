from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


IMMUTABLE_SECURITY_PREFIXES = (
    'jarvis/security/',
    'jarvis/self_development/policies.py',
    'jarvis/self_development/rollback.py',
)

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

    Self-development can propose changes to security-core files, but normal sandbox
    automation refuses them. A human-controlled development process can still edit
    those files outside this engine when deliberately reviewing the security design.
    """

    def __init__(self) -> None:
        self.max_files_changed = max(1, int(os.getenv('MAX_FILES_CHANGED', '20')))
        self.max_lines_changed = max(20, int(os.getenv('MAX_LINES_CHANGED', '1200')))
        self.max_build_time = max(10, int(os.getenv('MAX_BUILD_TIME', '300')))
        self.require_approval_for_production = os.getenv(
            'REQUIRE_APPROVAL_FOR_PRODUCTION', 'true'
        ).strip().lower() in {'1', 'true', 'yes', 'on'}

    @staticmethod
    def normalize(path: str | Path) -> str:
        raw = str(path).replace('\\', '/').lstrip('./')
        try:
            return str(PurePosixPath(raw))
        except Exception:
            return raw

    def path_allowed(self, path: str | Path) -> tuple[bool, str]:
        value = self.normalize(path)
        lower = value.lower()
        if lower == '.env' or lower.startswith('.env.'):
            return False, 'environment/secret files are protected'
        if any(lower.startswith(prefix.lower()) for prefix in IMMUTABLE_SECURITY_PREFIXES):
            return False, 'immutable security/rollback policy path'
        if any(lower.startswith(prefix.lower()) for prefix in PROTECTED_PRODUCTION_PREFIXES):
            return False, 'protected production/runtime data path'
        if '..' in PurePosixPath(value).parts:
            return False, 'path traversal is not allowed'
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
        if self.require_approval_for_production:
            return bool(explicit_user_approval)
        # Even if config relaxes approval, activation is never allowed through this
        # policy unless the caller supplies an explicit affirmative decision.
        return bool(explicit_user_approval)
