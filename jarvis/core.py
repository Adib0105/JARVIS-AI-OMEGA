"""Public JARVIS OMEGA V7/V7.5 compatibility core.

`JarvisOmega` preserves the established public API while layering verified missions,
security, memory, capability awareness, evaluation, observability, skill proposals
and bounded self-development over the provider-neutral core.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable

from .agent.context import ContextManager
from .agent.orchestrator_memory import MemoryAwareMissionOrchestrator
from .agent.tool_runtime import RecordingToolRegistry
from .capability_registry import CapabilityRegistry
from .config import settings
from .core_v7 import JarvisOmega as _ProviderCore
from .evaluation import CapabilityGapDetector, SelfEvaluationEngine
from .memory_v7 import MemoryKind, V7MemoryStore
from .observability import JarvisHealthSystem, ObservabilityManager
from .prompt import system_prompt
from .providers.observed import ObservedProvider
from .providers.router import ModelRouter
from .skills import SkillRegistry, WorkflowLearningEngine


class JarvisOmega(_ProviderCore):
    def __init__(self, confirmer: Callable[[str, dict], object] | None = None):
        super().__init__(confirmer=confirmer)
        db_path = self.memory.db_path
        self.memory = V7MemoryStore(db_path)
        self.context_manager = ContextManager(self.memory)
        self.capability_registry = CapabilityRegistry()
        self.model_router = ModelRouter()
        self.observability = ObservabilityManager(db_path)

        # Wrap already-created providers instead of rewriting the stable provider core.
        # The wrapper records normalized success/failure/latency/usage and explicit
        # provider-reported cost only. It never stores prompts or secrets.
        self.provider = ObservedProvider(
            self.provider,
            self.observability,
            context_provider=self._model_observability_context,
            fallback=False,
        )
        if self.local_provider is not None:
            self.local_provider = ObservedProvider(
                self.local_provider,
                self.observability,
                context_provider=self._model_observability_context,
                fallback=True,
            )

        self.tools = RecordingToolRegistry(
            self.memory,
            confirmer,
            context_provider=self._tool_audit_context,
        )
        self.orchestrator = MemoryAwareMissionOrchestrator(self)
        self.evaluation = SelfEvaluationEngine(
            db_path,
            mission_store=self.orchestrator.store,
            audit_store=self.tools.audit,
            capability_registry=self.capability_registry,
        )
        self.gap_detector = CapabilityGapDetector(
            db_path,
            evaluation=self.evaluation,
            missions=self.orchestrator.store,
            audit=self.tools.audit,
            registry=self.capability_registry,
        )
        self.health_system = JarvisHealthSystem(db_path, registry=self.capability_registry)
        self.skill_registry = SkillRegistry(db_path)
        self.workflow_learning = WorkflowLearningEngine(db_path, audit_store=self.tools.audit)

        # Self-development stays lazy because packaged/frozen installs may not have
        # Git or a repository checkout. Normal chat must not depend on those tools.
        self._self_development_engine = None
        self.last_mission_id: str | None = None
        self.last_context_stats: dict = {}

    def _select_model(self, text: str, kind: str = 'chat') -> str:
        """Use the V7.5 category router while keeping the V6/V7 method contract."""
        route = self.model_router.select(text, kind)
        self.last_route = route.category.lower()
        return route.model or settings.model

    def _latest_user_request(self) -> str:
        try:
            for role, content in reversed(self.memory.recent_messages(self.session_id, 12)):
                if role == 'user':
                    return str(content)
        except Exception:
            pass
        return ''

    def _system_instructions(self) -> str:
        prompt = system_prompt()
        try:
            prompt += '\n\nV7 CAPABILITY REGISTRY:\n' + self.capability_registry.summary_for_prompt()
        except Exception:
            # Capability inspection must never make normal chat unavailable.
            pass

        request = self._latest_user_request()
        orchestrator = getattr(self, 'orchestrator', None)
        mission_id = getattr(orchestrator, 'current_mission_id', None) or ''
        if request:
            try:
                bundle = self.context_manager.build(
                    session_id=self.session_id,
                    current_request=request,
                    mission_id=mission_id,
                )
                self.last_context_stats = {
                    'characters': bundle.characters,
                    'memory_count': bundle.memory_count,
                    'knowledge_count': bundle.knowledge_count,
                }
                if bundle.text:
                    prompt += '\n\nV7 LOCAL CONTEXT BUNDLE:\n' + bundle.text
            except Exception:
                pass
        return prompt

    def capability_status(self, *, refresh: bool = True) -> list[dict]:
        return self.capability_registry.snapshot(refresh=refresh)

    def evaluate_self(self, *, mission_limit: int = 100, audit_limit: int = 1000, persist: bool = True) -> dict:
        return self.evaluation.evaluate(
            mission_limit=mission_limit,
            audit_limit=audit_limit,
            persist=persist,
        ).as_dict()

    def evaluation_history(self, limit: int = 50) -> list[dict]:
        return self.evaluation.history(limit)

    def detect_capability_gaps(self, *, mission_limit: int = 100, audit_limit: int = 1000, persist: bool = True) -> list[dict]:
        return [
            gap.as_dict() for gap in self.gap_detector.detect(
                mission_limit=mission_limit,
                audit_limit=audit_limit,
                persist=persist,
            )
        ]

    def capability_gap_history(self, limit: int = 100) -> list[dict]:
        return self.gap_detector.list_open(limit)

    def observability_snapshot(self) -> dict:
        return self.observability.dashboard_snapshot()

    def model_usage(self, period: str = 'today', *, mission_id: str | None = None) -> dict:
        return self.observability.usage_summary(period, mission_id=mission_id)

    def health_check(self) -> dict:
        return self.health_system.run().as_dict()

    def detect_repeated_workflows(self, *, audit_limit: int = 1000, min_occurrences: int = 3, persist: bool = True) -> list[dict]:
        return [
            item.as_dict() for item in self.workflow_learning.detect(
                audit_limit=audit_limit,
                min_occurrences=min_occurrences,
                persist=persist,
            )
        ]

    def workflow_proposals(self, limit: int = 100) -> list[dict]:
        return self.workflow_learning.recent(limit)

    def propose_skill_from_gap(self, gap: dict) -> dict:
        """Create only a persisted inactive skill proposal; no skill is silently activated."""
        return self.skill_registry.propose_from_gap(dict(gap)).as_dict()

    def skill_proposals(self, limit: int = 100) -> list[dict]:
        return self.skill_registry.recent(limit)

    def _get_self_development_engine(self):
        if not settings.self_development_enabled:
            raise RuntimeError('Controlled self-development is disabled by configuration.')
        if self._self_development_engine is None:
            from .self_development import SelfDevelopmentEngine
            try:
                self._self_development_engine = SelfDevelopmentEngine(self.memory.db_path)
            except Exception as exc:
                raise RuntimeError(
                    'Self-development sandbox is unavailable in this installation. '
                    f'Git/repository/workspace check failed: {type(exc).__name__}: {exc}'
                ) from exc
        return self._self_development_engine

    def propose_improvement(self, gap: dict) -> dict:
        proposal = self._get_self_development_engine().proposal_from_gap(dict(gap))
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='proposal.created', status='SUCCESS',
            session_id=self.session_id, mission_id=self.last_mission_id,
            metadata={'proposal_id': proposal.id, 'capability': proposal.capability, 'risk': proposal.risk},
        )
        return proposal.as_dict()

    def prepare_improvement_sandbox(self, proposal_id: str) -> dict:
        proposal = self._get_self_development_engine().prepare_sandbox(proposal_id)
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='sandbox.prepared', status='SUCCESS',
            session_id=self.session_id, metadata={'proposal_id': proposal.id, 'branch': proposal.branch},
        )
        return proposal.as_dict()

    def run_self_coding(self, proposal_id: str) -> dict:
        """Generate/repair code in the proposal sandbox; production is never merged here."""
        from .self_development.coding import SelfCodingEngine

        engine = self._get_self_development_engine()

        def reasoner(system: str, user: str) -> str:
            return self._one_shot_text(system, user, 'coding')

        started = time.perf_counter()
        try:
            result = SelfCodingEngine(engine, reasoner).run(proposal_id)
            self.observability.record(
                category='SELF_DEVELOPMENT', event_type='self_coding.completed', status=result.status.value,
                session_id=self.session_id,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                metadata={'proposal_id': proposal_id, 'changed_files': len(result.changed_files)},
            )
            return result.as_dict()
        except Exception as exc:
            self.observability.record(
                category='SELF_DEVELOPMENT', event_type='self_coding.failed', status='FAILED',
                session_id=self.session_id,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                metadata={'proposal_id': proposal_id, 'error_type': type(exc).__name__},
            )
            raise

    def offline_development_status(self) -> dict:
        from .self_development.offline import OfflineDevelopmentRuntime
        return OfflineDevelopmentRuntime().status().as_dict()

    def run_offline_self_coding(self, proposal_id: str) -> dict:
        from .self_development.coding import SelfCodingEngine
        from .self_development.offline import OfflineDevelopmentRuntime

        engine = self._get_self_development_engine()
        offline = OfflineDevelopmentRuntime()
        offline.require_ready()
        result = SelfCodingEngine(engine, offline.reason).run(proposal_id)
        return result.as_dict()

    def self_development_proposals(self, limit: int = 50) -> list[dict]:
        return self._get_self_development_engine().recent(limit)

    def self_development_proposal(self, proposal_id: str) -> dict | None:
        return self._get_self_development_engine().get(proposal_id)

    def approve_improvement_for_release(self, proposal_id: str, *, explicit_user_approval: bool) -> dict:
        """Mark reviewed proposal approved; this still does not deploy it to production."""
        proposal = self._get_self_development_engine().approve(
            proposal_id,
            explicit_user_approval=explicit_user_approval,
        )
        return proposal.as_dict()

    def reject_improvement(self, proposal_id: str) -> dict:
        return self._get_self_development_engine().reject(proposal_id).as_dict()

    def _model_observability_context(self) -> dict:
        orchestrator = getattr(self, 'orchestrator', None)
        return {
            'session_id': getattr(self, 'session_id', None),
            'mission_id': getattr(orchestrator, 'current_mission_id', None),
            'route': getattr(self, 'last_route', ''),
        }

    def _tool_audit_context(self) -> dict:
        request_summary = self._latest_user_request()[:800]
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
        started = time.perf_counter()
        self.observability.record(
            category='MISSION', event_type='mission.started', status='RUNNING',
            session_id=self.session_id, metadata={'goal_chars': len(str(goal))},
        )
        try:
            mission = self.orchestrator.run(goal, progress)
            self.last_mission_id = mission.id
            self.memory.add_message(
                self.session_id,
                'assistant',
                f'[V7 MISSION {mission.id}]\n{mission.final_report}',
            )
            try:
                self.memory.remember_v7(
                    mission.final_report,
                    kind=MemoryKind.EPISODIC,
                    importance=0.8,
                    confidence=0.95 if mission.final_verification and mission.final_verification.verified else 0.65,
                    source=f'mission:{mission.id}',
                    metadata={
                        'mission_id': mission.id,
                        'status': mission.status.value,
                        'verification': mission.final_verification.status if mission.final_verification else 'UNKNOWN',
                    },
                    verified=bool(mission.final_verification and mission.final_verification.verified),
                )
            except Exception:
                pass
            self.observability.record(
                category='MISSION', event_type='mission.finished', status=mission.status.value,
                session_id=self.session_id, mission_id=mission.id,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                metadata={
                    'retry_count': mission.retry_count,
                    'recovery_count': mission.recovery_count,
                    'verification': mission.final_verification.status if mission.final_verification else 'UNKNOWN',
                },
            )
            return mission.final_report
        except Exception as exc:
            self.observability.record(
                category='MISSION', event_type='mission.failed', status='FAILED',
                session_id=self.session_id,
                latency_ms=round((time.perf_counter() - started) * 1000, 3),
                metadata={'error_type': type(exc).__name__},
            )
            raise

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
