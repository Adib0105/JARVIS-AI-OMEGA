from __future__ import annotations

import os

from .audit import AuditStore
from .capabilities import TOOL_SECURITY, RiskLevel
from .policy import DEFAULT_POLICIES, policy_for, trusted_local_mode_enabled


class SecurityCenter:
    """Read-only normalized security posture for UI/diagnostics."""

    def __init__(self, audit: AuditStore | None = None) -> None:
        self.audit = audit or AuditStore()

    @staticmethod
    def policies() -> list[dict]:
        rows = []
        for capability in sorted(DEFAULT_POLICIES, key=lambda item: item.value):
            default = DEFAULT_POLICIES[capability]
            current = policy_for(capability)
            rows.append({
                'capability': capability.value,
                'default': default.value,
                'effective': current.value,
                'overridden': current != default,
                'env': f'PERMISSION_{capability.value}',
            })
        return rows

    @staticmethod
    def dangerous_capabilities() -> list[dict]:
        rows = []
        for name, profile in sorted(TOOL_SECURITY.items()):
            if profile.risk not in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
                continue
            rows.append({
                'tool': name,
                'risk': profile.risk.value,
                'capabilities': sorted(item.value for item in profile.capabilities),
                'side_effecting': profile.side_effecting,
                'why': profile.why,
            })
        return rows

    def snapshot(self, limit: int = 200) -> dict:
        audit_rows = self.audit.list_entries(limit=max(1, min(int(limit), 1000)))
        blocked = [
            row for row in audit_rows
            if str(row.get('execution_status', '')).upper() in {'DENIED', 'FAILED'}
            or str(row.get('approval_status', '')).upper() in {'DENY', 'BLOCKED_SECRET'}
        ]
        approvals = [
            row for row in audit_rows
            if str(row.get('approval_status', '')).upper() not in {'AUTO_ALLOWED', 'NOT_RECORDED', ''}
        ]
        try:
            integrity = self.audit.verify_integrity()
        except Exception as exc:
            integrity = {
                'ok': False,
                'status': 'ERROR',
                'reason': f'{type(exc).__name__}: {exc}',
            }
        return {
            'trusted_local_mode': trusted_local_mode_enabled(),
            'require_local_approval': os.getenv('REQUIRE_LOCAL_APPROVAL', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
            'audit_integrity': integrity,
            'policies': self.policies(),
            'dangerous_tools': self.dangerous_capabilities(),
            'recent_blocked': blocked[:50],
            'approval_history': approvals[:100],
            'recent_audit': audit_rows[:100],
        }
