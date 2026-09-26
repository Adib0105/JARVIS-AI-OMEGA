"""Ordered AI -> ML -> Deep Learning -> Generative AI -> LLM runtime."""
from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ..retrieval import configured_embedding_backend
from ..security.secrets import contains_secret
from .adaptive import AdaptiveIntentModel, MLPrediction


FIVE_LAYER_NAMES = (
    'Artificial Intelligence',
    'Machine Learning',
    'Deep Learning',
    'Generative AI',
    'Large Language Model',
)


@dataclass(frozen=True)
class SemanticPrediction:
    category: str
    confidence: float
    scores: dict[str, float]

    def as_dict(self) -> dict:
        return asdict(self)


class SemanticRouter(Protocol):
    enabled: bool

    @property
    def available(self) -> bool: ...
    def predict(self, text: str) -> SemanticPrediction | None: ...
    def status(self) -> dict: ...


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    left = math.sqrt(sum(x * x for x in a))
    right = math.sqrt(sum(x * x for x in b))
    return dot / (left * right) if left and right else 0.0


class NeuralSemanticRouter:
    """Optional embedding-based route signal; never enabled silently."""

    PROTOTYPES = {
        'FAST': 'short casual conversation direct factual answer quick command',
        'SMART': 'complex analysis deep explanation comparison research reasoning',
        'CODING': 'software code debugging tests repository implementation architecture',
        'PLANNING': 'plan roadmap strategy ordered steps mission schedule milestones',
        'REVIEW': 'review audit verify validate quality evidence correctness',
        'SUMMARY': 'summarize recap condense overview key points',
    }

    def __init__(self, *, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self._lock = threading.RLock()
        self._prototype_vectors: dict[str, list[float]] | None = None
        self.last_error = ''
        self._backend = None
        if self.enabled:
            try:
                self._backend = configured_embedding_backend()
            except Exception as exc:
                # An optional semantic backend must never prevent desktop startup.
                self.last_error = f'{type(exc).__name__}: {exc}'

    @property
    def available(self) -> bool:
        return bool(self.enabled and self._backend is not None)

    def _prototypes(self) -> dict[str, list[float]]:
        with self._lock:
            if self._prototype_vectors is None:
                assert self._backend is not None
                categories = list(self.PROTOTYPES)
                vectors = self._backend.embed([self.PROTOTYPES[item] for item in categories])
                if len(vectors) != len(categories):
                    raise RuntimeError('Embedding endpoint returned an incomplete prototype batch.')
                self._prototype_vectors = dict(zip(categories, vectors))
            return dict(self._prototype_vectors)

    def predict(self, text: str) -> SemanticPrediction | None:
        if not self.available or not str(text).strip():
            return None
        try:
            assert self._backend is not None
            query = self._backend.embed([str(text)])[0]
            raw = {category: max(-1.0, min(1.0, _cosine(query, vector)))
                   for category, vector in self._prototypes().items()}
            shifted = {category: max(0.0, (score + 1.0) / 2.0) for category, score in raw.items()}
            total = sum(shifted.values()) or 1.0
            distribution = {category: round(value / total, 6) for category, value in shifted.items()}
            category = max(raw, key=raw.get)
            self.last_error = ''
            # Confidence is calibrated cosine similarity; ``scores`` remains a
            # normalized comparison across prototypes for diagnostics.
            return SemanticPrediction(category, round(float(shifted[category]), 6), distribution)
        except Exception as exc:
            self.last_error = f'{type(exc).__name__}: {exc}'
            return None

    def status(self) -> dict:
        return {
            'enabled': self.enabled,
            'available': self.available,
            'backend': type(self._backend).__name__ if self._backend is not None else '',
            'last_error': self.last_error,
        }


@dataclass(frozen=True)
class LayerTrace:
    order: int
    name: str
    status: str
    role: str
    detail: str
    confidence: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IntelligenceDecision:
    category: str
    model: str
    confidence: float
    reason: str
    generation_mode: str
    tool_strategy: str
    created_at: str
    layers: tuple[LayerTrace, ...]

    def as_dict(self) -> dict:
        data = asdict(self)
        data['layers'] = [layer.as_dict() for layer in self.layers]
        return data

    def prompt_summary(self) -> str:
        lines = [
            'FIVE-LAYER ROUTE (runtime metadata, not a claim of guaranteed correctness):',
            f'- Final route: {self.category}; model: {self.model}; confidence: {self.confidence:.2f}',
            f'- Generation mode: {self.generation_mode}; tools: {self.tool_strategy}',
        ]
        for layer in self.layers:
            lines.append(f'- {layer.order}. {layer.name}: {layer.status} — {layer.detail}')
        return '\n'.join(lines)


class FiveLayerIntelligence:
    """Fuses deterministic policy, local ML, optional semantics and model routing.

    The five labels are a taxonomy with concrete runtime responsibilities; they
    are not five separately billed foundation models.  Safety/capability policy
    remains outside model choice and cannot be overridden by a prediction.
    """

    _GENERATION_MODES = {
        'FAST': 'conversational_generation',
        'SMART': 'deep_reasoning',
        'CODING': 'code_generation',
        'PLANNING': 'structured_planning',
        'REVIEW': 'evidence_review',
        'SUMMARY': 'context_compression',
        'VISION': 'multimodal_analysis',
        'LOCAL': 'local_generation',
        'DEFAULT': 'provider_default',
    }

    def __init__(self, *, config, router, model_path: Path, semantic_router: SemanticRouter | None = None) -> None:
        self.config = config
        self.router = router
        self.enabled = bool(getattr(config, 'enable_five_layer_intelligence', True))
        self.ml = AdaptiveIntentModel(
            model_path,
            enabled=bool(getattr(config, 'enable_adaptive_ml_routing', True)),
            max_observations=int(getattr(config, 'adaptive_ml_max_observations', 5000)),
        )
        self.semantic = semantic_router or NeuralSemanticRouter(
            enabled=bool(getattr(config, 'enable_neural_semantic_routing', False))
        )
        self.last_decision: IntelligenceDecision | None = None

    def _provider_ready(self) -> bool:
        if self.config.provider == 'local':
            return bool(self.config.local_ai_model and self.config.local_ai_base_url)
        key = str(self.config.api_key).strip()
        placeholders = {
            'put_your_openrouter_key_here',
            'put_your_api_key_here',
            'yahan_apni_openrouter_key',
        }
        if key and key.casefold() not in placeholders:
            return True
        return bool(self.config.enable_local_fallback and self.config.local_ai_model and self.config.local_ai_base_url)

    def _model_for(self, category: str, fallback: str) -> str:
        mapping = {
            'FAST': self.config.routed_fast_model,
            'SMART': self.config.routed_smart_model,
            'CODING': self.config.routed_coding_model,
            'PLANNING': self.config.routed_planning_model,
            'REVIEW': self.config.routed_review_model,
            'SUMMARY': self.config.routed_summary_model,
            'VISION': self.config.routed_vision_model,
            'LOCAL': self.config.local_ai_model,
            'DEFAULT': self.config.model,
        }
        return str(mapping.get(category) or fallback or self.config.model)

    @staticmethod
    def _specific(category: str) -> bool:
        return category in {'CODING', 'PLANNING', 'REVIEW', 'SUMMARY', 'VISION', 'LOCAL'}

    def decide(self, text: str, kind: str = 'chat') -> IntelligenceDecision:
        base = self.router.select(text, kind)
        if not self.enabled:
            decision = IntelligenceDecision(
                base.category,
                base.model,
                1.0,
                'five-layer intelligence disabled; deterministic router used',
                self._GENERATION_MODES.get(base.category, 'provider_default'),
                'permission_gated' if self.config.enable_local_tools else 'no_tools',
                datetime.now(timezone.utc).isoformat(),
                tuple(LayerTrace(i, name, 'DISABLED', 'Disabled by configuration', 'Legacy deterministic route retained.')
                      for i, name in enumerate(FIVE_LAYER_NAMES, 1)),
            )
            self.last_decision = decision
            return decision

        ml_prediction: MLPrediction = self.ml.predict(text)
        secret_like_request = contains_secret(text)
        # Even an explicitly configured embedding service is an additional data
        # destination, so secret-like text never goes through semantic routing.
        semantic_prediction = None if secret_like_request else self.semantic.predict(text)
        category = base.category
        reasons = [base.reason]
        threshold = float(getattr(self.config, 'adaptive_ml_min_confidence', 0.72))
        neural_threshold = float(getattr(self.config, 'neural_routing_min_confidence', 0.76))

        # Explicit/specialized routes are policy-stable. ML may upgrade a generic
        # route but cannot downgrade vision/local/review/etc.  A neural signal can
        # only influence selection when it agrees with the local ML signal.
        if not self._specific(category) and ml_prediction.category != 'FAST' and ml_prediction.confidence >= threshold:
            category = ml_prediction.category
            reasons.append(f'local ML={category} ({ml_prediction.confidence:.2f})')
        if (
            not self._specific(base.category)
            and semantic_prediction is not None
            and semantic_prediction.category == ml_prediction.category
            and semantic_prediction.category != 'FAST'
            and semantic_prediction.confidence >= neural_threshold
        ):
            category = semantic_prediction.category
            reasons.append(f'neural semantic consensus={category} ({semantic_prediction.confidence:.2f})')

        model = self._model_for(category, base.model)
        provider_ready = self._provider_ready()
        generation_mode = self._GENERATION_MODES.get(category, 'provider_default')
        tool_strategy = 'permission_gated_tools' if self.config.enable_local_tools and category != 'SUMMARY' else 'no_tools'
        if self._specific(base.category):
            confidence = 0.98
        elif category != base.category:
            confidence = max(0.5, ml_prediction.confidence)
        else:
            confidence = max(0.55, min(0.95, 0.55 + ml_prediction.confidence * 0.35))

        semantic_status = self.semantic.status()
        deep_status = 'ACTIVE' if provider_ready else 'DEGRADED'
        semantic_detail = (
            f"semantic router active via {semantic_status.get('backend')}"
            if semantic_status.get('available') else
            'LLM/vision neural backbone selected; semantic embedding router is opt-in or unavailable'
        )
        if secret_like_request:
            semantic_detail = 'semantic routing skipped for secret-like request content'
        if semantic_status.get('last_error'):
            semantic_detail += '; last semantic error was contained and deterministic routing continued'

        layers = (
            LayerTrace(1, FIVE_LAYER_NAMES[0], 'ACTIVE', 'Executive intent, context, tools and safety orchestration',
                       f'intent={base.category}; deterministic reason={base.reason}', 1.0),
            LayerTrace(2, FIVE_LAYER_NAMES[1], 'LEARNING' if self.ml.enabled else 'DISABLED',
                       'Private local adaptive intent classification',
                       f'prediction={ml_prediction.category}; hashed observations={ml_prediction.learned_observations}; raw prompts stored=false',
                       ml_prediction.confidence),
            LayerTrace(3, FIVE_LAYER_NAMES[2], deep_status,
                       'Neural semantic, vision and representation capability',
                       f'provider={self.config.provider}; {semantic_detail}',
                       semantic_prediction.confidence if semantic_prediction else None),
            LayerTrace(4, FIVE_LAYER_NAMES[3], 'ACTIVE' if provider_ready else 'DEGRADED',
                       'Grounded content/code/plan/review generation strategy',
                       f'mode={generation_mode}; context=hybrid memory; tools={tool_strategy}'),
            LayerTrace(5, FIVE_LAYER_NAMES[4], 'ACTIVE' if provider_ready else 'DEGRADED',
                       'Final fast/smart/specialist language-model selection',
                       f'route={category}; model={model}', confidence),
        )
        decision = IntelligenceDecision(
            category,
            model,
            round(confidence, 6),
            '; '.join(reasons),
            generation_mode,
            tool_strategy,
            datetime.now(timezone.utc).isoformat(),
            layers,
        )
        self.last_decision = decision
        return decision

    def observe(self, text: str, category: str, *, success: bool) -> bool:
        return self.ml.learn(text, category, success=success)

    def reset_adaptive_model(self) -> dict:
        self.ml.reset()
        self.last_decision = None
        return self.status()

    def status(self) -> dict:
        ml = self.ml.stats()
        semantic = self.semantic.status()
        provider_ready = self._provider_ready()
        if self.last_decision is not None:
            layers = [item.as_dict() for item in self.last_decision.layers]
            last = self.last_decision.as_dict()
        else:
            layers = [
                LayerTrace(1, FIVE_LAYER_NAMES[0], 'ACTIVE' if self.enabled else 'DISABLED', 'Executive orchestration', 'Agent, memory, tools and policy integration.').as_dict(),
                LayerTrace(2, FIVE_LAYER_NAMES[1], 'LEARNING' if ml['enabled'] else 'DISABLED', 'Adaptive routing', f"hashed observations={ml['observations']}; raw prompts stored=false").as_dict(),
                LayerTrace(3, FIVE_LAYER_NAMES[2], 'ACTIVE' if provider_ready else 'DEGRADED', 'Neural inference', f"provider={self.config.provider}; semantic_router={semantic['available']}").as_dict(),
                LayerTrace(4, FIVE_LAYER_NAMES[3], 'ACTIVE' if provider_ready else 'DEGRADED', 'Generative strategy', 'Grounded chat/code/plan/review/vision modes.').as_dict(),
                LayerTrace(5, FIVE_LAYER_NAMES[4], 'ACTIVE' if provider_ready else 'DEGRADED', 'Model routing', f'primary model={self.config.model}').as_dict(),
            ]
            last = None
        return {
            'enabled': self.enabled,
            'layer_count': 5,
            'layers': layers,
            'adaptive_ml': ml,
            'neural_semantic_router': semantic,
            'last_decision': last,
            'taxonomy_note': 'AI contains ML; ML contains deep learning; generative AI and LLM are neural capabilities, not five independent models.',
            'safety_note': 'Routing never bypasses capability permissions, approvals, audit or verification.',
        }
