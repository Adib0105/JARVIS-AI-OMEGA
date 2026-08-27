from __future__ import annotations

from typing import Protocol, runtime_checkable

from .common.results import OperationResult


@runtime_checkable
class PermissionDecision(Protocol):
    """Minimal permission decision contract shared by legacy and capability gates."""

    allowed: bool
    reason: str


@runtime_checkable
class PermissionChecker(Protocol):
    """Boundary used by tool runtimes instead of depending on one gate implementation."""

    def check(self, name: str, args: dict) -> PermissionDecision:
        ...


@runtime_checkable
class ToolRuntime(Protocol):
    """Legacy provider/agent-facing tool contract retained for compatibility."""

    def schemas(self, include_local: bool = True) -> list[dict]:
        ...

    def call(self, name: str, args: dict) -> str:
        ...


@runtime_checkable
class EvidenceAwareToolRuntime(ToolRuntime, Protocol):
    """V8 migration contract exposing canonical operation result semantics."""

    def call_result(self, name: str, args: dict) -> OperationResult:
        ...


__all__ = [
    'PermissionChecker', 'PermissionDecision', 'ToolRuntime',
    'EvidenceAwareToolRuntime',
]
