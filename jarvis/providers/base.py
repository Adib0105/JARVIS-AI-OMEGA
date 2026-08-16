from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    output: str


@dataclass
class ProviderTurn:
    text: str = ''
    tool_calls: list[ToolCall] = field(default_factory=list)
    state: Any = None
    model: str = ''
    provider: str = ''
    usage: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Provider-neutral model interface used by JARVIS V7.

    Provider implementations may use different SDK endpoints internally, but the
    agent receives normalized text/tool-call turns and never needs SDK-specific
    response objects.
    """

    name: str

    @abstractmethod
    def chat(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        timeout: float,
    ) -> ProviderTurn:
        raise NotImplementedError

    @abstractmethod
    def chat_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        tools: list[dict],
        timeout: float,
    ) -> ProviderTurn:
        raise NotImplementedError

    @abstractmethod
    def continue_with_tools(
        self,
        *,
        previous: ProviderTurn,
        tool_results: list[ToolResult],
        system: str,
        model: str,
        tools: list[dict],
        timeout: float,
    ) -> ProviderTurn:
        raise NotImplementedError

    @abstractmethod
    def vision(
        self,
        *,
        system: str,
        prompt: str,
        image_urls: list[str],
        model: str,
        timeout: float,
    ) -> ProviderTurn:
        raise NotImplementedError

    def structured_output(
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        timeout: float,
    ) -> str:
        return self.chat(
            system=system,
            messages=[{'role': 'user', 'content': prompt}],
            model=model,
            timeout=timeout,
        ).text
