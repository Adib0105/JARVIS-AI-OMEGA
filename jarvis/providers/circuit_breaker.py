from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Callable


class CircuitState(str, Enum):
    CLOSED = 'CLOSED'
    OPEN = 'OPEN'
    HALF_OPEN = 'HALF_OPEN'


class CircuitOpenError(RuntimeError):
    def __init__(self, provider: str, retry_after: float, detail: str = '') -> None:
        self.provider = provider
        self.retry_after = max(0.0, float(retry_after))
        suffix = f' {detail}' if detail else ''
        super().__init__(
            f'Provider circuit open for {provider}; retry after approximately '
            f'{self.retry_after:.1f}s.{suffix}'
        )


@dataclass(frozen=True)
class CircuitSnapshot:
    provider: str
    state: str
    consecutive_retryable_failures: int
    failure_threshold: int
    recovery_seconds: float
    retry_after: float
    half_open_probe_in_flight: bool

    def as_dict(self) -> dict:
        return asdict(self)


class ProviderCircuitBreaker:
    """Thread-safe CLOSED → OPEN → HALF_OPEN provider failure circuit.

    Only retryable/provider-health failures should be counted. Non-retryable input,
    permission or policy failures do not poison provider health. After cooldown one
    HALF_OPEN probe is allowed; concurrent probes are rejected until it finishes.
    """

    def __init__(
        self,
        provider: str,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.provider = str(provider or 'provider')[:120]
        self.failure_threshold = max(1, min(int(failure_threshold), 20))
        self.recovery_seconds = max(1.0, min(float(recovery_seconds), 3600.0))
        self._clock = clock
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_probe = False

    def _retry_after_locked(self, now: float | None = None) -> float:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return 0.0
        now = self._clock() if now is None else now
        return max(0.0, self.recovery_seconds - (now - self._opened_at))

    def before_call(self) -> None:
        with self._lock:
            now = self._clock()
            if self._state == CircuitState.OPEN:
                remaining = self._retry_after_locked(now)
                if remaining > 0:
                    raise CircuitOpenError(self.provider, remaining)
                self._state = CircuitState.HALF_OPEN
                self._half_open_probe = False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probe:
                    raise CircuitOpenError(
                        self.provider,
                        min(self.recovery_seconds, 1.0),
                        'A recovery probe is already in progress.',
                    )
                self._half_open_probe = True

    def record_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = None
            self._half_open_probe = False

    def record_failure(self, *, retryable: bool) -> None:
        with self._lock:
            if not retryable:
                # A provider response that failed because of request/policy/input
                # still proves the endpoint itself is reachable. A HALF_OPEN health
                # probe therefore closes the circuit instead of reopening it.
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.CLOSED
                    self._failures = 0
                    self._opened_at = None
                self._half_open_probe = False
                return

            self._failures += 1
            self._half_open_probe = False
            if self._state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()

    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return CircuitSnapshot(
                provider=self.provider,
                state=self._state.value,
                consecutive_retryable_failures=self._failures,
                failure_threshold=self.failure_threshold,
                recovery_seconds=self.recovery_seconds,
                retry_after=round(self._retry_after_locked(), 3),
                half_open_probe_in_flight=self._half_open_probe,
            )


__all__ = [
    'CircuitOpenError', 'CircuitSnapshot', 'CircuitState', 'ProviderCircuitBreaker',
]
