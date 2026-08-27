from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from typing import Iterator
from typing import TypeVar
from uuid import uuid4

T = TypeVar('T')


class RequestCancelledError(RuntimeError):
    """Raised when the operator cancels the active AI request."""


@dataclass
class RequestBudget:
    """One wall-clock budget shared by every operation in a user request."""

    timeout_seconds: float
    operation: str = 'AI request'
    request_id: str = field(default_factory=lambda: f'REQ-{uuid4().hex[:12].upper()}')
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.timeout_seconds = request_deadline_seconds(self.timeout_seconds)
        self.deadline = self.started_at + self.timeout_seconds

    def remaining(self) -> float:
        if self.cancel_event.is_set():
            raise RequestCancelledError(f'{self.operation} was cancelled.')
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError(
                f'{self.operation} exceeded the {self.timeout_seconds:g}s request deadline.'
            )
        return seconds

    def cancel(self) -> None:
        self.cancel_event.set()


_ACTIVE_REQUEST: ContextVar[RequestBudget | None] = ContextVar(
    'jarvis_active_request_budget', default=None,
)


def current_request_budget() -> RequestBudget | None:
    return _ACTIVE_REQUEST.get()


@contextmanager
def request_lifecycle(
    timeout: float,
    *,
    operation: str = 'AI request',
    request_id: str | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[RequestBudget]:
    """Create a request budget, or reuse the parent budget for nested work."""
    active = current_request_budget()
    if active is not None:
        yield active
        return
    budget = RequestBudget(
        timeout_seconds=timeout,
        operation=operation,
        request_id=request_id or f'REQ-{uuid4().hex[:12].upper()}',
        cancel_event=cancel_event or threading.Event(),
    )
    token = _ACTIVE_REQUEST.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_REQUEST.reset(token)


def request_deadline_seconds(value: float) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 60.0
    return max(1.0, seconds)


def transport_timeout_seconds(request_timeout: float) -> float:
    """Per-I/O inactivity timeout used by provider SDK transports.

    This is deliberately shorter than the wall-clock request deadline. SDK/http
    timeouts are generally inactivity/operation timeouts and therefore are not a
    substitute for an end-to-end deadline when a server trickles bytes or retries.
    """
    return min(request_deadline_seconds(request_timeout), 30.0)


def call_with_deadline(call: Callable[[], T], timeout: float, *, operation: str = 'AI provider request') -> T:
    """Run a blocking SDK call behind a strict wall-clock deadline.

    The SDK call still receives its own finite connection/read timeout. This outer
    guard guarantees the caller regains control even if retries or a trickling HTTP
    response keep the underlying synchronous SDK call alive beyond that timeout.
    The worker is daemonized so a pathological transport cannot block application
    shutdown.
    """
    active = current_request_budget()
    requested_budget = request_deadline_seconds(timeout)
    # A direct provider call retains the production 1-second minimum. Inside a
    # user request, later retries/continuations are clamped to the *remaining*
    # request budget instead of receiving a fresh timeout.
    budget = min(requested_budget, active.remaining()) if active is not None else requested_budget
    deadline = time.monotonic() + budget
    result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)
    context = copy_context()

    def runner() -> None:
        try:
            value = context.run(call)
            item: tuple[bool, object] = (True, value)
        except BaseException as exc:  # propagate the original provider exception
            item = (False, exc)
        try:
            result.put_nowait(item)
        except queue.Full:
            pass

    thread = threading.Thread(target=runner, name='jarvis-provider-request', daemon=True)
    thread.start()
    if active is None:
        try:
            ok, value = result.get(timeout=budget)
        except queue.Empty as exc:
            raise TimeoutError(f'{operation} exceeded the {budget:g}s request deadline.') from exc
    else:
        while True:
            active_remaining = active.remaining()
            remaining = min(deadline - time.monotonic(), active_remaining)
            if remaining <= 0:
                raise TimeoutError(f'{operation} exceeded the {budget:g}s request deadline.')
            try:
                ok, value = result.get(timeout=min(0.1, remaining))
                break
            except queue.Empty:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'{operation} exceeded the {budget:g}s request deadline.')
    if ok:
        return value  # type: ignore[return-value]
    assert isinstance(value, BaseException)
    raise value
