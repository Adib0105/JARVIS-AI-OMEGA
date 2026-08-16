from __future__ import annotations

import time
from typing import Callable

from ..errors import classify_exception
from ..observability.manager import ObservabilityManager
from .base import AIProvider, ProviderTurn, ToolResult
from .circuit_breaker import CircuitOpenError, ProviderCircuitBreaker


class ObservedProvider(AIProvider):
    """Transparent AIProvider wrapper with telemetry and failure circuit control."""

    def __init__(
        self,
        provider: AIProvider,
        observability: ObservabilityManager,
        *,
        context_provider: Callable[[], dict] | None = None,
        fallback: bool = False,
        circuit_breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self.provider = provider
        self.observability = observability
        self.context_provider = context_provider or (lambda: {})
        self.fallback = bool(fallback)
        self.name = provider.name
        self.client = getattr(provider, 'client', None)
        self.circuit_breaker = circuit_breaker or ProviderCircuitBreaker(self.name)

    def _context(self) -> dict:
        try:
            return dict(self.context_provider() or {})
        except Exception:
            return {}

    def circuit_status(self) -> dict:
        return self.circuit_breaker.snapshot().as_dict()

    def _before_call(self, event_type: str, model: str) -> None:
        try:
            self.circuit_breaker.before_call()
        except CircuitOpenError as exc:
            context = self._context()
            self.observability.record_model_turn(
                event_type=event_type,
                status='BLOCKED',
                session_id=context.get('session_id'),
                mission_id=context.get('mission_id'),
                provider=self.name,
                model=model,
                latency_ms=0.0,
                usage=None,
                fallback=self.fallback,
                route=context.get('route'),
                error_category='CIRCUIT_OPEN',
            )
            raise

    def _record_success(self, event_type: str, model: str, started: float, turn: ProviderTurn) -> ProviderTurn:
        self.circuit_breaker.record_success()
        context = self._context()
        self.observability.record_model_turn(
            event_type=event_type,
            status='SUCCESS',
            session_id=context.get('session_id'),
            mission_id=context.get('mission_id'),
            provider=turn.provider or self.name,
            model=turn.model or model,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            usage=turn.usage,
            fallback=self.fallback,
            route=context.get('route'),
        )
        return turn

    def _record_failure(self, event_type: str, model: str, started: float, exc: BaseException) -> None:
        context = self._context()
        failure = classify_exception(exc, provider=self.name, operation=event_type)
        self.circuit_breaker.record_failure(retryable=failure.retryable)
        self.observability.record_model_turn(
            event_type=event_type,
            status='FAILED',
            session_id=context.get('session_id'),
            mission_id=context.get('mission_id'),
            provider=self.name,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            usage=None,
            fallback=self.fallback,
            route=context.get('route'),
            error_category=failure.category.value,
        )

    def chat(self, *, system: str, messages: list[dict], model: str, timeout: float) -> ProviderTurn:
        self._before_call('chat', model)
        started = time.perf_counter()
        try:
            turn = self.provider.chat(system=system, messages=messages, model=model, timeout=timeout)
            return self._record_success('chat', model, started, turn)
        except Exception as exc:
            self._record_failure('chat', model, started, exc)
            raise

    def chat_with_tools(self, *, system: str, messages: list[dict], model: str, tools: list[dict], timeout: float) -> ProviderTurn:
        self._before_call('chat_with_tools', model)
        started = time.perf_counter()
        try:
            turn = self.provider.chat_with_tools(
                system=system, messages=messages, model=model, tools=tools, timeout=timeout,
            )
            return self._record_success('chat_with_tools', model, started, turn)
        except Exception as exc:
            self._record_failure('chat_with_tools', model, started, exc)
            raise

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
        self._before_call('continue_with_tools', model)
        started = time.perf_counter()
        try:
            turn = self.provider.continue_with_tools(
                previous=previous,
                tool_results=tool_results,
                system=system,
                model=model,
                tools=tools,
                timeout=timeout,
            )
            return self._record_success('continue_with_tools', model, started, turn)
        except Exception as exc:
            self._record_failure('continue_with_tools', model, started, exc)
            raise

    def vision(self, *, system: str, prompt: str, image_urls: list[str], model: str, timeout: float) -> ProviderTurn:
        self._before_call('vision', model)
        started = time.perf_counter()
        try:
            turn = self.provider.vision(
                system=system, prompt=prompt, image_urls=image_urls, model=model, timeout=timeout,
            )
            return self._record_success('vision', model, started, turn)
        except Exception as exc:
            self._record_failure('vision', model, started, exc)
            raise

    def structured_output(self, *, system: str, prompt: str, model: str, timeout: float) -> str:
        # Use the normalized chat method so usage/cost telemetry and circuit health
        # are retained rather than delegating to an opaque provider-specific helper.
        turn = self.chat(
            system=system,
            messages=[{'role': 'user', 'content': prompt}],
            model=model,
            timeout=timeout,
        )
        return turn.text
