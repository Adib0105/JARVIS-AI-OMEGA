from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .config import settings
from .v10_runtime import AgentState, runtime


class CompanionMode(str, Enum):
    ACTIVE = 'active'
    SLEEP = 'sleep'
    DND = 'do_not_disturb'
    PRIVACY = 'privacy'


@dataclass
class CompanionSnapshot:
    mode: CompanionMode = CompanionMode.ACTIVE
    muted: bool = False
    listening: bool = False


class CompanionController:
    """V10 user-facing companion state. Safety controls always win over convenience."""

    def __init__(self) -> None:
        self._state = CompanionSnapshot()

    def snapshot(self) -> CompanionSnapshot:
        return CompanionSnapshot(**self._state.__dict__)

    def set_mode(self, mode: CompanionMode) -> None:
        self._state.mode = mode
        if mode is CompanionMode.PRIVACY:
            runtime.set_privacy(True)
            self._state.listening = False
        else:
            runtime.set_privacy(False)
        if mode in {CompanionMode.SLEEP, CompanionMode.DND}:
            runtime.cancel_current()
            self._state.listening = False

    def set_muted(self, value: bool) -> None:
        self._state.muted = bool(value)

    def can_listen(self) -> bool:
        snap = runtime.snapshot()
        return (
            not snap.emergency_stop
            and not snap.privacy_mode
            and self._state.mode is CompanionMode.ACTIVE
            and settings.enable_mic_input
        )

    def begin_listening(self) -> bool:
        if not self.can_listen():
            return False
        runtime.clear_cancel()
        runtime.transition(AgentState.LISTENING)
        self._state.listening = True
        return True

    def end_listening(self) -> None:
        self._state.listening = False
        if not runtime.snapshot().emergency_stop:
            runtime.transition(AgentState.IDLE)


def smart_greeting(now: datetime | None = None, user_name: str | None = None) -> str:
    now = now or datetime.now()
    name = (user_name or settings.user_name).strip()
    hour = now.hour
    if 5 <= hour < 12:
        greeting = 'Good morning'
    elif 12 <= hour < 17:
        greeting = 'Good afternoon'
    elif 17 <= hour < 22:
        greeting = 'Good evening'
    else:
        greeting = 'Hey'
    return f'{greeting}, {name}.' if name else f'{greeting}.'


companion = CompanionController()
