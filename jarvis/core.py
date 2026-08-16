"""Public JARVIS OMEGA V7 compatibility core.

`JarvisOmega` keeps the existing import/API surface while layering the V7 mission
orchestrator, evidence-recording tools, capability permissions and audit context
over the provider-neutral core.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from .agent.orchestrator import MissionOrchestrator
from .agent.tool_runtime import RecordingToolRegistry
from .core_v7 import JarvisOmega as _ProviderCore


class JarvisOmega(_ProviderCore):
    def __init__(self, confirmer: Callable[[str, dict], object] | None = None):
        super().__init__(confirmer=confirmer)
        self.tools = RecordingToolRegistry(
            self.memory,
            confirmer,
            context_provider=self._tool_audit_context,
        )
        self.orchestrator = MissionOrchestrator(self)
        self.last_mission_id: str | None = None

    def _tool_audit_context(self) -> dict:
        request_summary = ''
        try:
            rows = self.memory.recent_messages(self.session_id)
            for role, content in reversed(rows):
                if role == 'user':
                    request_summary = str(content)[:800]
                    break
        except Exception:
            pass
        orchestrator = getattr(self, 'orchestrator', None)
        return {
            'session_id': self.session_id,
            'mission_id': getattr(orchestrator, 'current_mission_id', None),
            'request_summary': request_summary,
            'provider': getattr(self, 'last_provider_used', None),
            'model': getattr(self, 'last_model_used', None),
        }

    @staticmethod
    def _extract_plan(raw: str, max_steps: int) -> list[str]:
        """Structured-first plan parser that correctly preserves an intentional empty plan."""
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                parsed = parsed.get('steps', [])
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()][:max_steps]
        except Exception:
            pass
        return _ProviderCore._extract_plan(raw, max_steps)

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
