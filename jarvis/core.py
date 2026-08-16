"""Public JARVIS OMEGA V7 compatibility core.

`JarvisOmega` keeps the existing import/API surface while layering the V7 mission
orchestrator and evidence-recording tool runtime over the provider-neutral core.
"""

from __future__ import annotations

from typing import Callable

from .agent.orchestrator import MissionOrchestrator
from .agent.tool_runtime import RecordingToolRegistry
from .core_v7 import JarvisOmega as _ProviderCore


class JarvisOmega(_ProviderCore):
    def __init__(self, confirmer: Callable[[str, dict], bool] | None = None):
        super().__init__(confirmer=confirmer)
        self.tools = RecordingToolRegistry(self.memory, confirmer)
        self.orchestrator = MissionOrchestrator(self)
        self.last_mission_id: str | None = None

    def run_mission(self, goal: str, progress: Callable[[str], None] | None = None) -> str:
        mission = self.orchestrator.run(goal, progress)
        self.last_mission_id = mission.id
        self.memory.add_message(
            self.session_id,
            'assistant',
            f'[V7 MISSION {mission.id}]\n{mission.final_report}',
        )
        return mission.final_report

    def cancel_mission(self, mission_id: str | None = None) -> bool:
        return self.orchestrator.cancel(mission_id)

    def pause_mission(self, mission_id: str | None = None) -> bool:
        return self.orchestrator.pause(mission_id)

    def resume_mission(self, mission_id: str | None = None) -> bool:
        return self.orchestrator.resume(mission_id)

    def get_mission(self, mission_id: str):
        return self.orchestrator.get(mission_id)

    def recent_missions(self, limit: int = 20) -> list[dict]:
        return self.orchestrator.recent(limit)


__all__ = ['JarvisOmega']
