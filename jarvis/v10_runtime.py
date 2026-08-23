from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Event, RLock
from time import monotonic


class AgentState(str, Enum):
    IDLE='idle'; LISTENING='listening'; THINKING='thinking'; SPEAKING='speaking'; EXECUTING='executing'; VERIFYING='verifying'; ERROR='error'; STOPPED='stopped'


@dataclass(frozen=True)
class Capability:
    key: str
    title: str
    enabled: bool = True
    sensitive: bool = False
    requires_network: bool = False


V10_CAPABILITIES = {
    c.key: c for c in (
        Capability('live_companion','Live Companion'), Capability('barge_in','Instant Barge-In'),
        Capability('streaming_voice','Streaming Voice', requires_network=True), Capability('wake_word','Wake Word'),
        Capability('screen_awareness','Screen Awareness', sensitive=True), Capability('computer_use','Computer Use', sensitive=True),
        Capability('browser_agent','Browser Agent', sensitive=True), Capability('file_agent','Advanced File Agent', sensitive=True),
        Capability('research','Research Agent', requires_network=True), Capability('documents','Document Intelligence'),
        Capability('coding','Coding Agent', sensitive=True), Capability('memory','Personal Memory', sensitive=True),
        Capability('missions','Mission Agent'), Capability('multi_agent','Multi-Agent Brain'), Capability('verification','Automatic Verification'),
        Capability('local_ai','Local AI'), Capability('rag','Knowledge/RAG'), Capability('self_evaluation','Self Evaluation'),
        Capability('self_development','Controlled Self Development', sensitive=True), Capability('audit','Audit Trail'),
        Capability('backup','Backup/Restore'), Capability('google_workspace','Google Workspace', sensitive=True, requires_network=True),
        Capability('automation','Workflow Automation', sensitive=True), Capability('multimodal','Multimodal Input'),
    )
}


@dataclass
class RuntimeSnapshot:
    state: AgentState = AgentState.IDLE
    privacy_mode: bool = False
    emergency_stop: bool = False
    active_mission: str | None = None
    last_transition: float = field(default_factory=monotonic)


class V10Runtime:
    """Thread-safe V10 control plane. It never bypasses existing permission gates."""
    def __init__(self) -> None:
        self._lock = RLock(); self._cancel = Event(); self._snapshot = RuntimeSnapshot()

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            return RuntimeSnapshot(**self._snapshot.__dict__)

    def transition(self, state: AgentState) -> None:
        with self._lock:
            if self._snapshot.emergency_stop and state is not AgentState.STOPPED:
                return
            self._snapshot.state = state; self._snapshot.last_transition = monotonic()

    def cancel_current(self) -> None:
        self._cancel.set()

    def clear_cancel(self) -> None:
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def set_privacy(self, enabled: bool) -> None:
        with self._lock:
            self._snapshot.privacy_mode = bool(enabled)
        if enabled:
            self.cancel_current()

    def emergency_stop(self) -> None:
        with self._lock:
            self._snapshot.emergency_stop = True; self._snapshot.state = AgentState.STOPPED; self._snapshot.last_transition = monotonic()
        self._cancel.set()

    def resume_after_stop(self) -> None:
        with self._lock:
            self._snapshot.emergency_stop = False; self._snapshot.state = AgentState.IDLE; self._snapshot.last_transition = monotonic()
        self._cancel.clear()

    def capability_status(self) -> list[dict]:
        return [c.__dict__.copy() for c in V10_CAPABILITIES.values()]


runtime = V10Runtime()
