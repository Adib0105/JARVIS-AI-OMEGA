from __future__ import annotations

from dataclasses import dataclass


SENSITIVE_CATEGORIES = frozenset({
    'money', 'credential', 'account', 'delete', 'email_send', 'calendar_write',
    'code_write', 'git_write', 'system_change', 'install', 'uninstall',
})


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


def classify_action(category: str, *, explicit_user_request: bool = False) -> SecurityDecision:
    """Convenience never silently bypasses high-impact action protection."""
    key = (category or '').strip().lower()
    if key in SENSITIVE_CATEGORIES:
        return SecurityDecision(
            allowed=bool(explicit_user_request),
            requires_confirmation=True,
            reason='Sensitive action requires an explicit user request and the existing permission gate.',
        )
    return SecurityDecision(True, False, 'Low-risk action may continue through normal capability and permission checks.')
