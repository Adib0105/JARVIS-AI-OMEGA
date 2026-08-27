from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar('T')


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
    budget = request_deadline_seconds(timeout)
    result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def runner() -> None:
        try:
            value = call()
            item: tuple[bool, object] = (True, value)
        except BaseException as exc:  # propagate the original provider exception
            item = (False, exc)
        try:
            result.put_nowait(item)
        except queue.Full:
            pass

    thread = threading.Thread(target=runner, name='jarvis-provider-request', daemon=True)
    thread.start()
    try:
        ok, value = result.get(timeout=budget)
    except queue.Empty as exc:
        raise TimeoutError(f'{operation} exceeded the {budget:g}s request deadline.') from exc
    if ok:
        return value  # type: ignore[return-value]
    assert isinstance(value, BaseException)
    raise value
