from __future__ import annotations

from typing import Callable

from .mission import Mission, MissionStatus
from .orchestrator import MissionOrchestrator


class MemoryAwareMissionOrchestrator(MissionOrchestrator):
    """Adds bounded mission working-memory updates to the Phase-2 orchestrator."""

    def _transition(
        self,
        mission: Mission,
        status: MissionStatus,
        progress: Callable[[str], None],
        detail: str = '',
    ) -> None:
        super()._transition(mission, status, progress, detail)
        setter = getattr(self.core.memory, 'set_working_memory', None)
        if callable(setter):
            try:
                setter(
                    mission.session_id,
                    'mission_state',
                    f'Status={mission.status.value}; goal={mission.goal}; current_step={mission.current_step}; detail={detail}',
                    mission_id=mission.id,
                    metadata={'mission_id': mission.id, 'status': mission.status.value},
                )
            except Exception:
                pass

    def run(self, goal: str, progress=None) -> Mission:
        mission = super().run(goal, progress)
        clearer = getattr(self.core.memory, 'clear_working_memory', None)
        if callable(clearer):
            try:
                clearer(mission.session_id, mission.id)
            except Exception:
                pass
        return mission
