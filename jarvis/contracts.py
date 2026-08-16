from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PermissionDecision(Protocol):
    """Minimal permission decision contract shared by legacy and V7 gates."""

    allowed: bool
    reason: str


@runtime_checkable
class PermissionChecker(Protocol):
    """Boundary used by tool runtimes instead of depending on one gate implementation."""

    def check(self, name: str, args: dict) -> PermissionDecision:
        ...


@runtime_checkable
class ToolRuntime(Protocol):
    """Provider/agent-facing tool runtime contract."""

    def schemas(self, include_local: bool = True) -> list[dict]:
        ...

    def call(self, name: str, args: dict) -> str:
        ...
