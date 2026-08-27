import unittest
from pathlib import Path
from types import SimpleNamespace

from jarvis.config_validation import ValidationLevel, validate_settings
from jarvis.core import JarvisOmega
from jarvis.errors import ErrorCategory, classify_exception
from jarvis.providers.base import ProviderTurn, ToolCall, ToolResult
from jarvis.providers.openrouter_provider import OpenRouterProvider


class FakeHTTPError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class V7FoundationTests(unittest.TestCase):
    def test_public_core_import_remains_compatible(self):
        self.assertEqual(JarvisOmega._extract_plan('["One", "Two"]', 5), ['One', 'Two'])

    def test_error_taxonomy_timeout_and_rate_limit(self):
        self.assertEqual(classify_exception(TimeoutError('timed out')).category, ErrorCategory.TIMEOUT)
        rate = classify_exception(FakeHTTPError('rate limited', 429))
        self.assertEqual(rate.category, ErrorCategory.RATE_LIMIT)
        self.assertTrue(rate.retryable)

    def test_error_taxonomy_permission_is_not_retryable(self):
        failure = classify_exception(PermissionError('blocked'))
        self.assertEqual(failure.category, ErrorCategory.PERMISSION_ERROR)
        self.assertFalse(failure.retryable)

    def test_provider_contract_dataclasses(self):
        call = ToolCall('abc', 'get_current_time', '{}')
        result = ToolResult('abc', '{"ok": true}')
        turn = ProviderTurn(text='', tool_calls=[call], provider='test')
        self.assertEqual(turn.tool_calls[0].name, 'get_current_time')
        self.assertEqual(result.call_id, 'abc')

    def test_openrouter_tool_schema_conversion(self):
        converted = OpenRouterProvider._tools([
            {
                'type': 'function',
                'name': 'demo',
                'description': 'Demo tool',
                'parameters': {'type': 'object', 'properties': {'q': {'type': 'string'}}},
            }
        ])
        self.assertEqual(converted[0]['function']['name'], 'demo')
        self.assertIn('parameters', converted[0]['function'])

    def test_configuration_validation_detects_fatal_problem(self):
        settings = SimpleNamespace(
            provider='bad-provider',
            model='',
            api_key='',
            ai_timeout_seconds=60.0,
            vision_timeout_seconds=75.0,
            mission_timeout_seconds=300.0,
            api_max_retries=2,
            max_tool_rounds=12,
            mission_max_steps=5,
            max_image_attachments=4,
            max_image_mb=12,
            image_max_dimension=1600,
            image_jpeg_quality=82,
            voice_volume=1.0,
            voice_english='en-IN-NeerjaNeural',
            voice_hinglish='en-IN-NeerjaNeural',
            voice_hindi='hi-IN-SwaraNeural',
            tts_timeout_seconds=180.0,
            offline_tts_timeout_seconds=90.0,
            mic_record_seconds=6.0,
            allowed_file_roots=(Path('.'),),
            enable_google_workspace=False,
            google_credentials_file=Path('missing.json'),
            enable_local_fallback=False,
            local_ai_base_url='',
            local_ai_model='',
        )
        findings = validate_settings(settings)
        failures = [x for x in findings if x.level == ValidationLevel.FAIL]
        self.assertTrue(any(x.key == 'AI_PROVIDER' for x in failures))
        self.assertTrue(any(x.key == 'MODEL' for x in failures))
        self.assertTrue(any(x.key == 'API_KEY' for x in failures))


if __name__ == '__main__':
    unittest.main()
