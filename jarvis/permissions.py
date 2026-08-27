from __future__ import annotations

from typing import Callable

from .config import settings
from .security.policy import CapabilityPermissionGate, PermissionOutcome

# Backward-compatible public name. There is intentionally no second SAFE/APPROVAL
# policy table here: all decisions are delegated to the canonical capability gate.
Decision = PermissionOutcome


class PermissionGate:
    """Legacy API adapter over the canonical V7 capability permission authority."""

    def __init__(self, confirmer: Callable[[str, dict], object] | None = None):
        self._canonical = CapabilityPermissionGate(
            confirmer,
            require_approval=settings.require_local_approval,
        )

    @property
    def confirmer(self):
        return self._canonical.confirmer

    def check(self, name: str, args: dict) -> PermissionOutcome:
        return self._canonical.check(name, args)

    def clear_session_grants(self) -> None:
        self._canonical.clear_session_grants()

    def consume_last_outcome(self) -> PermissionOutcome | None:
        return self._canonical.consume_last_outcome()
