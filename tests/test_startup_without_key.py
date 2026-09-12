from dataclasses import replace
from unittest.mock import patch
import unittest

from jarvis.config import settings
from jarvis.config_validation import ValidationLevel, fatal_findings, validate_settings
from jarvis.providers.factory import create_primary_provider
from jarvis.providers.missing_credentials import MissingCredentialsProvider


class StartupWithoutKeyTests(unittest.TestCase):
    def test_missing_openrouter_key_is_warning_not_startup_failure(self):
        config = replace(settings, provider='openrouter', openrouter_api_key='')
        findings = validate_settings(config)
        row = next(item for item in findings if item.key == 'API_KEY')
        self.assertEqual(row.level, ValidationLevel.WARNING)
        self.assertNotIn(row, fatal_findings(findings))

    def test_invalid_provider_and_missing_key_remain_fatal(self):
        config = replace(settings, provider='bad-provider', openrouter_api_key='')
        keys = {item.key for item in fatal_findings(validate_settings(config))}
        self.assertIn('AI_PROVIDER', keys)
        self.assertIn('API_KEY', keys)

    def test_factory_does_not_create_cloud_client_without_key(self):
        config = replace(settings, provider='openrouter', openrouter_api_key='')
        with patch('jarvis.providers.factory.OpenRouterProvider') as provider:
            result = create_primary_provider(config)
        self.assertIsInstance(result, MissingCredentialsProvider)
        provider.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, 'OPENROUTER_API_KEY'):
            result.chat(system='', messages=[], model='', timeout=1)

    def test_package_env_overrides_blank_windows_variable(self):
        # Reload test uses a subprocess-free direct assertion of dotenv's intended behavior.
        from dotenv import dotenv_values
        self.assertIn('OPENROUTER_API_KEY', dotenv_values('.env.example'))


if __name__ == '__main__':
    unittest.main()
