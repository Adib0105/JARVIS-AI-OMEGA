from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable

from ..memory import MemoryStore
from ..tools import ToolRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecordingToolRegistry(ToolRegistry):
    """Compatibility wrapper that records tool calls without changing V6 handlers."""

    def __init__(self, memory: MemoryStore, confirmer: Callable[[str, dict], bool] | None = None):
        super().__init__(memory, confirmer)
        self._events: list[dict] = []
        self._events_lock = threading.RLock()

    def call(self, name: str, args: dict) -> str:
        started = _now()
        output = super().call(name, args)
        event = {
            'name': name,
            'args': dict(args),
            'output': output,
            'started_at': started,
            'completed_at': _now(),
        }
        with self._events_lock:
            self._events.append(event)
        return output

    def clear_events(self) -> None:
        with self._events_lock:
            self._events.clear()

    def drain_events(self) -> list[dict]:
        with self._events_lock:
            events = list(self._events)
            self._events.clear()
        return events

    def snapshot_events(self) -> list[dict]:
        with self._events_lock:
            return list(self._events)
