import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.self_development.offline import OfflineDevelopmentRuntime, UNAVAILABLE_MESSAGE


class FakeProvider:
    def __init__(self):
        self.calls = []

    def structured_output(self, **kwargs):
        self.calls.append(kwargs)
        return '{"files":{"x.py":"x = 1\\n"}}'


def fake_settings(**overrides):
    values = dict(
        offline_development_enabled=True,
        local_ai_model='local-model',
        local_ai_base_url='http://127.0.0.1:11434/v1',
        local_model_provider='openai-compatible',
        local_ai_api_key='local',
        ai_timeout_seconds=30.0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class V75OfflineDevelopmentTests(unittest.TestCase):
    def test_missing_model_reports_exact_unavailable_message(self):
        runtime = OfflineDevelopmentRuntime(provider=FakeProvider())
        with patch('jarvis.self_development.offline.settings', fake_settings(local_ai_model='')):
            status = runtime.status()
            self.assertFalse(status.configured)
            self.assertEqual(status.message, UNAVAILABLE_MESSAGE)
            with self.assertRaisesRegex(RuntimeError, UNAVAILABLE_MESSAGE):
                runtime.reason('system', 'prompt')

    def test_disabled_mode_does_not_pretend_to_be_offline_ready(self):
        runtime = OfflineDevelopmentRuntime(provider=FakeProvider())
        with patch('jarvis.self_development.offline.settings', fake_settings(offline_development_enabled=False)):
            self.assertFalse(runtime.status().enabled)
            with self.assertRaisesRegex(RuntimeError, 'disabled by configuration'):
                runtime.reason('system', 'prompt')

    def test_configured_local_provider_is_used_without_network_install_logic(self):
        provider = FakeProvider()
        runtime = OfflineDevelopmentRuntime(provider=provider)
        with patch('jarvis.self_development.offline.settings', fake_settings()):
            output = runtime.reason('safe system', 'build locally')
        self.assertIn('x.py', output)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]['model'], 'local-model')
        self.assertEqual(provider.calls[0]['timeout'], 30.0)


if __name__ == '__main__':
    unittest.main()
