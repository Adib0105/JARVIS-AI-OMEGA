from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

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
    FeatureSpec(1, 'live_companion', 'Live Companion Mode', 'integrated'),
    FeatureSpec(2, 'barge_in', 'Instant Barge-In', 'integration'),
    FeatureSpec(3, 'low_latency_voice', 'Ultra-Low-Latency Voice', 'integration'),
    FeatureSpec(4, 'language_switch', 'Natural Hinglish + English', 'implemented'),
    FeatureSpec(5, 'conversation_style', 'Human-like Conversation Style', 'implemented'),
    FeatureSpec(6, 'voice_profiles', 'Multiple Voice Personalities', 'integration'),
    FeatureSpec(7, 'wake_word_v2', 'Wake Word V2', 'integration'),
    FeatureSpec(8, 'windows_autostart', 'Windows Auto-Start', 'integration'),
    FeatureSpec(9, 'smart_greeting', 'Smart Greeting Engine', 'implemented'),
    FeatureSpec(10, 'background_service', 'Background Companion Service', 'integration'),
    FeatureSpec(11, 'system_tray', 'System Tray JARVIS', 'integration'),
    FeatureSpec(12, 'screen_awareness', 'Screen Awareness', 'integrated'),
    FeatureSpec(13, 'context_understanding', 'Current Context Understanding', 'integrated'),
    FeatureSpec(14, 'computer_use_v3', 'Computer Use V3', 'integration'),
    FeatureSpec(15, 'visual_control', 'Visual Computer Control', 'integration'),
    FeatureSpec(16, 'multi_monitor', 'Multi-Monitor Awareness', 'integration'),
    FeatureSpec(17, 'application_control', 'Application Control', 'implemented'),
    FeatureSpec(18, 'file_agent', 'Advanced File Agent', 'integration'),
    FeatureSpec(19, 'browser_agent_v3', 'Browser Agent V3', 'integration'),
    FeatureSpec(20, 'research_agent', 'Research Agent', 'integration'),
    FeatureSpec(21, 'document_intelligence', 'Document Intelligence V3', 'integration'),
    FeatureSpec(22, 'coding_agent_v3', 'Coding Agent V3', 'integration'),
    FeatureSpec(23, 'personal_memory_v3', 'Personal Memory V3', 'integration'),
    FeatureSpec(24, 'memory_control', 'Memory Control Center', 'integration'),
    FeatureSpec(25, 'routine_learning', 'Routine Learning', 'integrated'),
)


class GroupAController:
    """V10 control plane for features 1-25.

    This class coordinates existing subsystems instead of duplicating them. It never
    bypasses their permission, privacy or sensitive-action gates.
    """

    def __init__(self) -> None:
        self.state = GroupAState()

    def feature_manifest(self) -> list[dict]:
        return [f.__dict__.copy() for f in GROUP_A_FEATURES]

    def feature_status(self, number: int) -> dict | None:
        for feature in GROUP_A_FEATURES:
            if feature.number == number:
                return feature.__dict__.copy()
        return None

    def readiness(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for feature in GROUP_A_FEATURES:
            counts[feature.status] = counts.get(feature.status, 0) + 1
        counts['total'] = len(GROUP_A_FEATURES)
        return counts

    def set_live_companion(self, enabled: bool) -> None:
        self.state.live_companion = bool(enabled)
        companion.set_mode(CompanionMode.ACTIVE if enabled else CompanionMode.SLEEP)

    def set_wake_word(self, enabled: bool) -> None:
        self.state.wake_word_enabled = bool(enabled)

    def set_startup(self, enabled: bool) -> None:
        self.state.startup_enabled = bool(enabled)

    def set_background(self, enabled: bool) -> None:
        self.state.background_enabled = bool(enabled)

    def set_tray(self, enabled: bool) -> None:
        self.state.tray_enabled = bool(enabled)

    def set_awareness(self, mode: AwarenessMode) -> None:
        self.state.awareness = mode
        if mode is AwarenessMode.OFF:
            self.clear_context()

    def update_context(
        self,
        *,
        app: str | None = None,
        resource: str | None = None,
        monitor: int | None = None,
    ) -> bool:
        if self.state.awareness is AwarenessMode.OFF or runtime.snapshot().privacy_mode:
            return False
        self.state.active_app = app
        self.state.active_resource = resource
        self.state.active_monitor = monitor
        return True

    def context_snapshot(self) -> dict[str, object | None]:
        if runtime.snapshot().privacy_mode or self.state.awareness is AwarenessMode.OFF:
            return {'app': None, 'resource': None, 'monitor': None}
        return {
            'app': self.state.active_app,
            'resource': self.state.active_resource,
            'monitor': self.state.active_monitor,
        }

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

    def list_routines(self) -> dict[str, list[str]]:
        return {name: list(steps) for name, steps in self.state.learned_routines.items()}

    def forget_routine(self, name: str) -> bool:
        return self.state.learned_routines.pop(name, None) is not None

    def resolve_context_reference(self, phrase: str) -> str | None:
        if runtime.snapshot().privacy_mode:
            return None
        normalized = phrase.strip().lower()
        if normalized in {
            'this', 'this file', 'isko', 'ise', 'ye', 'ye file', 'current file',
            'wahi file', 'same file',
        }:
            return self.state.active_resource
        if normalized in {'this app', 'current app', 'ye app', 'wahi app', 'same app'}:
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
