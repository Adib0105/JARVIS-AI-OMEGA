from .capabilities import Capability, RiskLevel, ToolSecurityProfile, profile_for
from .policy import ApprovalDecision, CapabilityPermissionGate, PermissionPolicy
from .secrets import contains_secret, detect_secrets, ensure_safe_for_persistent_memory

__all__ = [
    'AuditStore',
    'Capability',
    'RiskLevel',
    'ToolSecurityProfile',
    'profile_for',
    'ApprovalDecision',
    'CapabilityPermissionGate',
    'PermissionPolicy',
    'contains_secret',
    'detect_secrets',
    'ensure_safe_for_persistent_memory',
]


def __getattr__(name):
    # Logging imports security.redaction during desktop startup. Importing the
    # audit store eagerly here would recurse into a half-initialized logger.
    if name == 'AuditStore':
        from .audit import AuditStore
        return AuditStore
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
