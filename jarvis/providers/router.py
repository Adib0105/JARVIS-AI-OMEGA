from __future__ import annotations

from dataclasses import asdict, dataclass

from ..config import settings


@dataclass(frozen=True)
class ModelRoute:
    category: str
    model: str
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


class ModelRouter:
    """Deterministic route selector; provider switching remains explicit/fallback-only."""

    SMART_HINTS = {
        'analyze', 'analyse', 'debug', 'error', 'architecture', 'compare', 'reason',
        'why', 'research', 'security', 'document', 'problem', 'issue', 'advanced',
        'समझाओ', 'क्यों', 'विश्लेषण',
    }
    CODING_HINTS = {'code', 'coding', 'python', 'bug', 'test', 'repository', 'repo', 'refactor', 'function', 'class'}
    PLAN_HINTS = {'plan', 'mission', 'steps', 'roadmap', 'strategy'}
    REVIEW_HINTS = {'review', 'verify', 'verification', 'check result', 'evaluate'}
    SUMMARY_HINTS = {'summarize', 'summary', 'recap', 'shorten'}

    def select(self, text: str, kind: str = 'chat') -> ModelRoute:
        kind = (kind or 'chat').strip().lower()
        lower = str(text).lower()
        if kind in {'image', 'vision'}:
            return ModelRoute('VISION', settings.routed_vision_model, 'multimodal request')
        if kind in {'coding', 'code', 'self-coding'}:
            return ModelRoute('CODING', settings.routed_coding_model, 'coding workflow')
        if kind in {'planning', 'plan', 'mission', 'mission-plan'}:
            return ModelRoute('PLANNING', settings.routed_planning_model, 'mission/planning workflow')
        if kind in {'review', 'verification'}:
            return ModelRoute('REVIEW', settings.routed_review_model, 'review/verification workflow')
        if kind in {'summary', 'summarize'}:
            return ModelRoute('SUMMARY', settings.routed_summary_model, 'summary workflow')
        if kind in {'local', 'offline'}:
            return ModelRoute('LOCAL', settings.local_ai_model, 'explicit local/offline route')

        if settings.model_routing not in {'auto', 'on', 'true'}:
            return ModelRoute('DEFAULT', settings.model, 'model routing disabled')

        if any(hint in lower for hint in self.CODING_HINTS):
            return ModelRoute('CODING', settings.routed_coding_model, 'coding keywords')
        if any(hint in lower for hint in self.PLAN_HINTS):
            return ModelRoute('PLANNING', settings.routed_planning_model, 'planning keywords')
        if any(hint in lower for hint in self.REVIEW_HINTS):
            return ModelRoute('REVIEW', settings.routed_review_model, 'review keywords')
        if any(hint in lower for hint in self.SUMMARY_HINTS):
            return ModelRoute('SUMMARY', settings.routed_summary_model, 'summary keywords')
        smart = len(str(text)) > 700 or any(hint in lower for hint in self.SMART_HINTS)
        if smart:
            return ModelRoute('SMART', settings.routed_smart_model, 'complexity/analysis heuristic')
        return ModelRoute('FAST', settings.routed_fast_model, 'short/general request')
