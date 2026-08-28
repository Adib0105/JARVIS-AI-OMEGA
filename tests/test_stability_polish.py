from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from jarvis.config import settings
from jarvis.config_validation import ValidationLevel, validate_settings
from jarvis.updater import _parse_version, check_latest_release
from jarvis.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode('utf-8')


class StabilityPolishTests(unittest.TestCase):
    def test_release_version_order_handles_rc_and_final_semantics(self):
        self.assertLess(_parse_version('8.0.0-rc1'), _parse_version('8.0.0-rc2'))
        self.assertLess(_parse_version('v8.0.0-rc2'), _parse_version('8.0.0'))
        self.assertLess(_parse_version('8.0.0'), _parse_version('8.0.1'))

    def test_update_check_marks_final_release_newer_than_current_rc(self):
        payload = {
            'tag_name': 'v8.0.0',
            'html_url': 'https://github.com/Adib0105/JARVIS-AI-OMEGA/releases/tag/v8.0.0',
            'name': 'JARVIS AI OMEGA 8.0.0',
        }
        with patch('jarvis.updater.urllib.request.urlopen', return_value=_Response(payload)) as mocked:
            result = check_latest_release('8.0.0-rc1')
        self.assertTrue(result['available'])
        request = mocked.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), f'JARVIS-AI-OMEGA/{APP_VERSION}')

    def test_update_check_fails_closed_for_unrecognized_release_tag(self):
        payload = {'tag_name': 'latest-awesome', 'html_url': 'https://example.invalid/release'}
        with patch('jarvis.updater.urllib.request.urlopen', return_value=_Response(payload)):
            with self.assertRaises(RuntimeError):
                check_latest_release(APP_VERSION)

    def test_voice_env_template_matches_runtime_voice_phase(self):
        text = (ROOT / '.env.example').read_text(encoding='utf-8')
        for expected in (
            'VOICE_PROFILE=indian-female-emotional',
            'VOICE_EMOTION_ENABLED=true',
            'VOICE_STREAMING_ENABLED=true',
            'VOICE_BARGE_IN=true',
            'VOICE_CHUNK_CHARS=260',
            'WAKE_CHUNK_SECONDS=3.5',
            'VOICE_CONTINUOUS_SECONDS=18',
            'SPEECH_LANGUAGE=auto',
        ):
            self.assertIn(expected, text)
        self.assertNotIn('OPENROUTER_APP_TITLE=JARVIS AI OMEGA V7', text)

    def test_settings_ui_exposes_new_voice_controls_without_v6_branding(self):
        text = (ROOT / 'jarvis' / 'settings_ui.py').read_text(encoding='utf-8')
        for key in (
            'VOICE_PROFILE',
            'VOICE_EMOTION_ENABLED',
            'VOICE_STREAMING_ENABLED',
            'VOICE_BARGE_IN',
            'VOICE_CHUNK_CHARS',
            'WAKE_CHUNK_SECONDS',
            'VOICE_CONTINUOUS_SECONDS',
        ):
            self.assertIn(repr(key), text)
        self.assertNotIn('JARVIS V6', text)
        self.assertNotIn('V6 CORE SETTINGS', text)
        self.assertNotIn('JARVIS OMEGA V6', text)

    def test_voice_validation_rejects_out_of_range_runtime_timing(self):
        configured = replace(
            settings,
            voice_chunk_chars=20,
            wake_chunk_seconds=1.0,
            voice_continuous_seconds=90.0,
        )
        findings = {item.key: item for item in validate_settings(configured)}
        self.assertEqual(findings['VOICE_CHUNK_CHARS'].level, ValidationLevel.FAIL)
        self.assertEqual(findings['WAKE_CHUNK_SECONDS'].level, ValidationLevel.FAIL)
        self.assertEqual(findings['VOICE_CONTINUOUS_SECONDS'].level, ValidationLevel.FAIL)

    def test_packaging_is_a_direct_runtime_dependency_for_semver_comparison(self):
        requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
        self.assertIn('packaging==26.3', requirements)


if __name__ == '__main__':
    unittest.main()
