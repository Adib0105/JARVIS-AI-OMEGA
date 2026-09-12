from dataclasses import replace
from unittest.mock import patch
import unittest

from jarvis.config import settings
from jarvis.config_validation import fatal_findings, validate_settings
from jarvis.providers.factory import create_primary_provider, create_local_provider
from jarvis.providers.router import ModelRouter


class LocalAIAndRoutingTests(unittest.TestCase):
    def test_local_provider_needs_no_cloud_credentials(self):
        config = replace(settings, provider='local', local_ai_model='installed-model',
                         openai_api_key='', openrouter_api_key='')
        self.assertFalse(fatal_findings(validate_settings(config)))
        self.assertEqual(config.model, 'installed-model')
        self.assertEqual(config.base_url, config.local_ai_base_url)
        self.assertEqual(config.api_key, config.local_ai_api_key)
        with patch('jarvis.providers.factory.LocalProvider') as factory:
            create_primary_provider(config)
        self.assertEqual(factory.call_args.kwargs['base_url'], config.local_ai_base_url)
        self.assertIsNone(create_local_provider(config))

    def test_local_requires_model_and_endpoint(self):
        config = replace(settings, provider='local', local_ai_model='', local_ai_base_url='')
        keys = {f.key for f in fatal_findings(validate_settings(config))}
        self.assertIn('LOCAL_AI_MODEL', keys)
        self.assertIn('LOCAL_AI_BASE_URL', keys)

    def test_invalid_voice_engine_is_reported(self):
        findings = validate_settings(replace(settings, voice_engine='typo'))
        self.assertIn('VOICE_ENGINE', {f.key for f in fatal_findings(findings)})

    def test_substrings_do_not_trigger_expensive_routes(self):
        with patch('jarvis.providers.router.settings', replace(settings, model_routing='auto')):
            for text in ['What is the latest news?', 'Tell me about a planet', 'I love classical music', 'How are you?']:
                with self.subTest(text=text):
                    self.assertEqual(ModelRouter().select(text).category, 'FAST')

    def test_whole_terms_still_route_correctly(self):
        with patch('jarvis.providers.router.settings', replace(settings, model_routing='auto')):
            for text, category in [('Debug Python code', 'CODING'), ('Plan my day', 'PLANNING'), ('Review this', 'REVIEW'), ('Summarize this', 'SUMMARY'), ('क्यों ऐसा होता है', 'SMART')]:
                self.assertEqual(ModelRouter().select(text).category, category)
