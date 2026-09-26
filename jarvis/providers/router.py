from __future__ import annotations

import re

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

    def __init__(self, config=None) -> None:
        self.config = config or settings

    SMART_HINTS = {
        'analyze', 'analyse', 'debug', 'error', 'architecture', 'compare', 'reason',
        'why', 'research', 'security', 'document', 'problem', 'issue', 'advanced',
        'समझाओ', 'क्यों', 'विश्लेषण',
    }
    CODING_HINTS = {'code', 'coding', 'python', 'bug', 'test', 'repository', 'repo', 'refactor', 'function', 'class'}
    PLAN_HINTS = {'plan', 'mission', 'steps', 'roadmap', 'strategy'}
    REVIEW_HINTS = {'review', 'verify', 'verification', 'check result', 'evaluate'}
    SUMMARY_HINTS = {'summarize', 'summary', 'recap', 'shorten'}

    @staticmethod
    def _matches(text: str, hints: set[str]) -> bool:
        # Whole terms: 'latest' is not 'test', 'planet' is not 'plan'.
        return any(re.search(r'(?<!\w)' + re.escape(hint) + r'(?!\w)', text) for hint in hints)

    def select(self, text: str, kind: str = 'chat') -> ModelRoute:
        kind = (kind or 'chat').strip().lower()
        lower = str(text).lower()
        if kind in {'image', 'vision'}:
            return ModelRoute('VISION', self.config.routed_vision_model, 'multimodal request')
        if kind in {'coding', 'code', 'self-coding'}:
            return ModelRoute('CODING', self.config.routed_coding_model, 'coding workflow')
        if kind in {'planning', 'plan', 'mission', 'mission-plan'}:
            return ModelRoute('PLANNING', self.config.routed_planning_model, 'mission/planning workflow')
        if kind in {'review', 'verification'}:
            return ModelRoute('REVIEW', self.config.routed_review_model, 'review/verification workflow')
        if kind in {'summary', 'summarize'}:
            return ModelRoute('SUMMARY', self.config.routed_summary_model, 'summary workflow')
        if kind in {'local', 'offline'}:
            return ModelRoute('LOCAL', self.config.local_ai_model, 'explicit local/offline route')

        if self.config.model_routing not in {'auto', 'on', 'true'}:
            return ModelRoute('DEFAULT', self.config.model, 'model routing disabled')

        if self._matches(lower, self.CODING_HINTS):
            return ModelRoute('CODING', self.config.routed_coding_model, 'coding keywords')
        if self._matches(lower, self.PLAN_HINTS):
            return ModelRoute('PLANNING', self.config.routed_planning_model, 'planning keywords')
        if self._matches(lower, self.REVIEW_HINTS):
            return ModelRoute('REVIEW', self.config.routed_review_model, 'review keywords')
        if self._matches(lower, self.SUMMARY_HINTS):
            return ModelRoute('SUMMARY', self.config.routed_summary_model, 'summary keywords')
        smart = len(str(text)) > 700 or self._matches(lower, self.SMART_HINTS)
        if smart:
            return ModelRoute('SMART', self.config.routed_smart_model, 'complexity/analysis heuristic')
        return ModelRoute('FAST', self.config.routed_fast_model, 'short/general request')
