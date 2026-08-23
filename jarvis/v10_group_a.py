from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from .v10_companion import CompanionMode, companion
from .v10_runtime import runtime


class AwarenessMode(str, Enum):
    OFF = 'off'
    ON_DEMAND = 'on_demand'
    ACTIVE_SESSION = 'active_session'


@dataclass
class GroupAState:
    live_companion: bool = False
    wake_word_enabled: bool = False
    startup_enabled: bool = False
    background_enabled: bool = False
    tray_enabled: bool = True
    awareness: AwarenessMode = AwarenessMode.OFF
    active_monitor: int | None = None
    active_app: str | None = None
    active_resource: str | None = None
    learned_routines: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSpec:
    number: int
    key: str
    title: str
    status: str


GROUP_A_FEATURES = (
    FeatureSpec(1, 'live_companion', 'Live Companion Mode', 'foundation'),
    FeatureSpec(2, 'barge_in', 'Instant Barge-In', 'foundation'),
    FeatureSpec(3, 'low_latency_voice', 'Ultra-Low-Latency Voice', 'foundation'),
    FeatureSpec(4, 'language_switch', 'Natural Hinglish + English', 'implemented'),
    FeatureSpec(5, 'conversation_style', 'Human-like Conversation Style', 'implemented'),
    FeatureSpec(6, 'voice_profiles', 'Multiple Voice Personalities', 'foundation'),
    FeatureSpec(7, 'wake_word_v2', 'Wake Word V2', 'foundation'),
    FeatureSpec(8, 'windows_autostart', 'Windows Auto-Start', 'foundation'),
    FeatureSpec(9, 'smart_greeting', 'Smart Greeting Engine', 'implemented'),
    FeatureSpec(10, 'background_service', 'Background Companion Service', 'foundation'),
    FeatureSpec(11, 'system_tray', 'System Tray JARVIS', 'foundation'),
    FeatureSpec(12, 'screen_awareness', 'Screen Awareness', 'foundation'),
    FeatureSpec(13, 'context_understanding', 'Current Context Understanding', 'foundation'),
    FeatureSpec(14, 'computer_use_v3', 'Computer Use V3', 'foundation'),
    FeatureSpec(15, 'visual_control', 'Visual Computer Control', 'foundation'),
    FeatureSpec(16, 'multi_monitor', 'Multi-Monitor Awareness', 'foundation'),
    FeatureSpec(17, 'application_control', 'Application Control', 'implemented'),
    FeatureSpec(18, 'file_agent', 'Advanced File Agent', 'foundation'),
    FeatureSpec(19, 'browser_agent_v3', 'Browser Agent V3', 'foundation'),
    FeatureSpec(20, 'research_agent', 'Research Agent', 'foundation'),
    FeatureSpec(21, 'document_intelligence', 'Document Intelligence V3', 'foundation'),
    FeatureSpec(22, 'coding_agent_v3', 'Coding Agent V3', 'foundation'),
    FeatureSpec(23, 'personal_memory_v3', 'Personal Memory V3', 'foundation'),
    FeatureSpec(24, 'memory_control', 'Memory Control Center', 'foundation'),
    FeatureSpec(25, 'routine_learning', 'Routine Learning', 'foundation'),
)


class GroupAController:
    """Control plane for V10 features 1-25.

    It coordinates existing subsystems without granting new permissions. Screen,
    files, browser and computer-use actions must still pass their subsystem gates.
    """

    def __init__(self) -> None:
        self.state = GroupAState()

    def feature_manifest(self) -> list[dict]:
        return [f.__dict__.copy() for f in GROUP_A_FEATURES]

    def set_live_companion(self, enabled: bool) -> None:
        self.state.live_companion = bool(enabled)
        companion.set_mode(CompanionMode.ACTIVE if enabled else CompanionMode.SLEEP)

    def set_awareness(self, mode: AwarenessMode) -> None:
        self.state.awareness = mode
        if mode is AwarenessMode.OFF:
            self.clear_context()

    def update_context(self, *, app: str | None = None, resource: str | None = None, monitor: int | None = None) -> bool:
        if self.state.awareness is AwarenessMode.OFF or runtime.snapshot().privacy_mode:
            return False
        self.state.active_app = app
        self.state.active_resource = resource
        self.state.active_monitor = monitor
        return True

    def clear_context(self) -> None:
        self.state.active_app = None
        self.state.active_resource = None
        self.state.active_monitor = None

    def learn_routine(self, name: str, steps: list[str]) -> None:
        clean_name = name.strip()
        clean_steps = [step.strip() for step in steps if step.strip()]
        if not clean_name or not clean_steps:
            raise ValueError('Routine requires a name and at least one step.')
        self.state.learned_routines[clean_name] = clean_steps

    def forget_routine(self, name: str) -> bool:
        return self.state.learned_routines.pop(name, None) is not None

    def resolve_context_reference(self, phrase: str) -> str | None:
        normalized = phrase.strip().lower()
        if normalized in {'this', 'this file', 'isko', 'ye', 'ye file', 'current file'}:
            return self.state.active_resource
        if normalized in {'this app', 'current app', 'ye app'}:
            return self.state.active_app
        return None

    @staticmethod
    def safe_file_target(path: str, roots: list[str]) -> Path | None:
        candidate = Path(path).expanduser().resolve()
        for root in roots:
            base = Path(root).expanduser().resolve()
            try:
                candidate.relative_to(base)
                return candidate
            except ValueError:
                continue
        return None


group_a = GroupAController()
