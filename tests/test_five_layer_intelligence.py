import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from jarvis.capability_registry import CapabilityRegistry
from jarvis.config import settings
from jarvis.config_validation import fatal_findings, validate_settings
from jarvis.intelligence import (
    FIVE_LAYER_NAMES,
    AdaptiveIntentModel,
    FiveLayerIntelligence,
    NeuralSemanticRouter,
    SemanticPrediction,
)
from jarvis.observability.manager import ObservabilityManager
from jarvis.providers.router import ModelRouter


class FakeSemanticRouter:
    enabled = True
    available = True

    def __init__(self, category='CODING', confidence=0.95):
        self.category = category
        self.confidence = confidence
        self.calls = 0

    def predict(self, _text):
        self.calls += 1
        return SemanticPrediction(self.category, self.confidence, {self.category: self.confidence})

    def status(self):
        return {'enabled': True, 'available': True, 'backend': 'fake-embedding', 'last_error': ''}


class FiveLayerIntelligenceTests(unittest.TestCase):
    def config(self, **changes):
        base = dict(
            openrouter_api_key='test-key',
            enable_five_layer_intelligence=True,
            enable_adaptive_ml_routing=True,
            adaptive_ml_min_confidence=0.72,
            adaptive_ml_max_observations=5000,
            enable_neural_semantic_routing=False,
            neural_routing_min_confidence=0.76,
        )
        base.update(changes)
        return replace(settings, **base)

    def stack(self, folder, *, config=None, semantic=None):
        config = config or self.config()
        return FiveLayerIntelligence(
            config=config,
            router=ModelRouter(config=config),
            model_path=Path(folder) / 'adaptive-route-model.json',
            semantic_router=semantic or FakeSemanticRouter('FAST', 0.2),
        )

    def test_exact_five_layers_are_ordered_like_source_diagram(self):
        with tempfile.TemporaryDirectory() as folder:
            decision = self.stack(folder).decide('Explain this architecture in detail')
        self.assertEqual(tuple(layer.name for layer in decision.layers), FIVE_LAYER_NAMES)
        self.assertEqual(tuple(layer.order for layer in decision.layers), (1, 2, 3, 4, 5))
        self.assertEqual(decision.category, 'SMART')
        self.assertEqual(decision.generation_mode, 'deep_reasoning')

    def test_specialized_and_vision_routes_cannot_be_downgraded_by_ml(self):
        with tempfile.TemporaryDirectory() as folder:
            stack = self.stack(folder, semantic=FakeSemanticRouter('FAST', 0.99))
            self.assertEqual(stack.decide('debug this Python code').category, 'CODING')
            self.assertEqual(stack.decide('look at the attached image', 'image').category, 'VISION')

    def test_neural_route_requires_local_ml_consensus(self):
        with tempfile.TemporaryDirectory() as folder:
            disagreeing = self.stack(folder, semantic=FakeSemanticRouter('SUMMARY', 0.99))
            self.assertEqual(disagreeing.decide('analyze complex architecture evidence').category, 'SMART')

            agreeing = self.stack(folder, semantic=FakeSemanticRouter('SMART', 0.99))
            decision = agreeing.decide('analyze complex architecture evidence')
            self.assertEqual(decision.category, 'SMART')
            self.assertIn('neural semantic consensus=SMART', decision.reason)

    def test_secret_like_request_never_reaches_semantic_router(self):
        with tempfile.TemporaryDirectory() as folder:
            semantic = FakeSemanticRouter('SMART', 0.99)
            decision = self.stack(folder, semantic=semantic).decide('password=super-secret-123')
            self.assertEqual(semantic.calls, 0)
            self.assertIn('semantic routing skipped', decision.layers[2].detail)

    def test_optional_semantic_backend_failure_does_not_break_startup(self):
        with patch('jarvis.intelligence.stack.configured_embedding_backend', side_effect=RuntimeError('offline')):
            semantic = NeuralSemanticRouter(enabled=True)
        self.assertFalse(semantic.available)
        self.assertIn('RuntimeError', semantic.status()['last_error'])

    def test_successful_routes_adapt_to_private_user_vocabulary(self):
        phrase = 'zorbula quendrix navo'
        with tempfile.TemporaryDirectory() as folder:
            stack = self.stack(folder)
            self.assertEqual(stack.decide(phrase).category, 'FAST')
            for _ in range(12):
                self.assertTrue(stack.observe(phrase, 'CODING', success=True))
            decision = stack.decide(phrase)
            self.assertEqual(decision.category, 'CODING')
            self.assertGreater(decision.confidence, 0.72)
            self.assertIn('local ML=CODING', decision.reason)

    def test_adaptive_model_never_persists_raw_prompts_or_secrets(self):
        phrase = 'UniquePrivateProjectVocabulary'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'adaptive.json'
            model = AdaptiveIntentModel(path)
            self.assertTrue(model.learn(phrase, 'CODING', success=True))
            raw = path.read_text(encoding='utf-8')
            self.assertNotIn(phrase.lower(), raw.lower())
            before = json.loads(raw)['observations']
            self.assertFalse(model.learn('password=super-secret-123', 'FAST', success=True))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['observations'], before)
            self.assertFalse(model.stats()['raw_prompts_stored'])

    def test_corrupt_learning_file_degrades_without_breaking_routing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'adaptive.json'
            path.write_text('{broken', encoding='utf-8')
            model = AdaptiveIntentModel(path)
            self.assertEqual(model.predict('hello').category, 'FAST')
            self.assertTrue(model.stats()['load_error'])

    def test_failed_model_write_rolls_back_in_memory_learning(self):
        with tempfile.TemporaryDirectory() as folder:
            model = AdaptiveIntentModel(Path(folder) / 'adaptive.json')
            with patch.object(model, '_persist', side_effect=OSError('read only')):
                self.assertFalse(model.learn('custom coding vocabulary', 'CODING', success=True))
            self.assertEqual(model.observations, 0)

    def test_learned_feature_store_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            model = AdaptiveIntentModel(Path(folder) / 'adaptive.json')
            model.MAX_FEATURES_PER_CATEGORY = 3
            self.assertTrue(model.learn('alpha beta gamma delta epsilon', 'CODING', success=True))
            self.assertLessEqual(model.stats()['stored_feature_hashes'], 3)

    def test_reset_removes_only_adaptive_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            stack = self.stack(folder)
            stack.observe('custom route phrase', 'PLANNING', success=True)
            self.assertEqual(stack.status()['adaptive_ml']['observations'], 1)
            report = stack.reset_adaptive_model()
            self.assertEqual(report['adaptive_ml']['observations'], 0)
            self.assertFalse((Path(folder) / 'adaptive-route-model.json').exists())

    def test_configuration_bounds_are_enforced(self):
        broken = self.config(adaptive_ml_min_confidence=1.5, neural_routing_min_confidence=0.1)
        keys = {item.key for item in fatal_findings(validate_settings(broken))}
        self.assertIn('ADAPTIVE_ML_MIN_CONFIDENCE', keys)
        self.assertIn('NEURAL_ROUTING_MIN_CONFIDENCE', keys)

    def test_enabled_neural_route_reports_missing_embedding_configuration(self):
        with patch.dict(os.environ, {'EMBEDDING_BASE_URL': '', 'EMBEDDING_MODEL': ''}):
            findings = validate_settings(self.config(enable_neural_semantic_routing=True))
        warnings = {item.key for item in findings if item.level.value == 'WARNING'}
        self.assertIn('EMBEDDING_BASE_URL', warnings)
        self.assertIn('EMBEDDING_MODEL', warnings)

    def test_capability_and_observability_expose_stack_without_raw_text(self):
        record = CapabilityRegistry().get('Five-Layer Intelligence')
        self.assertIsNotNone(record)
        self.assertIn(record.status.value, {'AVAILABLE', 'DEGRADED', 'DISABLED'})
        with tempfile.TemporaryDirectory() as folder:
            obs = ObservabilityManager(Path(folder) / 'jarvis.db')
            event = obs.record(
                category='INTELLIGENCE', event_type='five_layer.route', status='SUCCESS',
                metadata={'route': 'CODING', 'raw_prompt_stored': False},
            )
            self.assertEqual(event.category, 'INTELLIGENCE')
            self.assertFalse(event.metadata['raw_prompt_stored'])


if __name__ == '__main__':
    unittest.main()
