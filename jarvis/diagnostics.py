from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DiagnosticState(str, Enum):
    INSTALLED = 'INSTALLED'
    CONFIGURED = 'CONFIGURED'
    LOCAL_FUNCTIONAL = 'LOCAL_FUNCTIONAL'
    INTEGRATION_TESTED = 'INTEGRATION_TESTED'
    DEVICE_VERIFIED = 'DEVICE_VERIFIED'
    E2E_VERIFIED = 'E2E_VERIFIED'
    DEGRADED = 'DEGRADED'
    FAILED = 'FAILED'
    NOT_TESTED = 'NOT_TESTED'


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    state: DiagnosticState
    detail: str = ''
    required: bool = False

    @property
    def failed(self) -> bool:
        return self.state == DiagnosticState.FAILED

    def line(self) -> str:
        suffix = f' - {self.detail}' if self.detail else ''
        return f'[{self.state.value}] {self.name}{suffix}'


__all__ = ['DiagnosticResult', 'DiagnosticState']
