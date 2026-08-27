from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from jarvis.first_run import inspect_bootstrap_state, save_ai_configuration, test_provider_connection
from jarvis.logging_utils import redact_text
from jarvis.product_paths import ProductPaths, config_env_path
from jarvis.settings_ui import update_env_values


class _Response:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False


def _ok_opener(request, timeout=0):
    assert timeout > 0
    assert request.get_header('Authorization')
    return _Response()


def _unauthorized_opener(request, timeout=0):
    raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, io.BytesIO(b''))


class FirstRunBootstrapTests(unittest.TestCase):
    def test_missing_api_key_requires_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('AI_PROVIDER=openrouter\nOPENROUTER_MODEL=openrouter/free\n', encoding='utf-8')
            state = inspect_bootstrap_state(path, environ={})
            self.assertFalse(state.ready)
            self.assertFalse(state.key_present)
            self.assertIn('API key', state.reason)

    def test_placeholder_api_key_is_not_valid_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('AI_PROVIDER=openrouter\nOPENROUTER_API_KEY=put_your_openrouter_key_here\n', encoding='utf-8')
            self.assertFalse(inspect_bootstrap_state(path, environ={}).ready)

    def test_invalid_provider_configuration_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('AI_PROVIDER=unknown\nOPENROUTER_API_KEY=not-a-placeholder\n', encoding='utf-8')
            state = inspect_bootstrap_state(path, environ={})
            self.assertFalse(state.ready)
            self.assertIn('provider', state.reason.lower())

    def test_valid_configuration_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('AI_PROVIDER=openrouter\nOPENROUTER_API_KEY=test-key-value\nOPENROUTER_MODEL=openrouter/free\n', encoding='utf-8')
            state = inspect_bootstrap_state(path, environ={})
            self.assertTrue(state.ready)
            self.assertTrue(state.key_present)
            self.assertTrue(state.model_present)

    def test_first_run_save_and_restart_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config' / '.env'
            saved = save_ai_configuration('openrouter', 'test-key-value', 'openrouter/free', path)
            self.assertEqual(saved, path)
            self.assertTrue(path.is_file())
            restarted = inspect_bootstrap_state(path, environ={})
            self.assertTrue(restarted.ready)
            text = path.read_text(encoding='utf-8')
            self.assertIn('AI_PROVIDER=openrouter', text)
            self.assertIn('OPENROUTER_MODEL=openrouter/free', text)

    def test_test_connection_valid_and_invalid_without_secret_in_message(self):
        secret = 'sk-or-v1-super-secret-test-value'
        ok, success = test_provider_connection('openrouter', secret, opener=_ok_opener)
        self.assertTrue(ok)
        self.assertNotIn(secret, success)
        ok, failure = test_provider_connection('openrouter', secret, opener=_unauthorized_opener)
        self.assertFalse(ok)
        self.assertNotIn(secret, failure)
        self.assertIn('rejected', failure)

    def test_secret_redaction_remains_effective_for_bootstrap_key_shapes(self):
        secret = 'sk-or-v1-super-secret-test-value'
        redacted = redact_text(f'OPENROUTER_API_KEY={secret} Authorization: Bearer {secret}')
        self.assertNotIn(secret, redacted)
        self.assertIn('[REDACTED]', redacted)

    def test_settings_update_is_atomic_allowlisted_and_preserves_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            secret = 'sk-or-v1-super-secret-test-value'
            path.write_text(
                f'AI_PROVIDER=openrouter\nOPENROUTER_API_KEY={secret}\nAI_TIMEOUT_SECONDS=60\n',
                encoding='utf-8',
            )
            with patch('jarvis.settings_ui._env_path', return_value=path):
                update_env_values({
                    'AI_TIMEOUT_SECONDS': '45',
                    'VOICE_ENGLISH': 'en-IN-NeerjaNeural',
                    'OPENROUTER_API_KEY': 'must-not-overwrite',
                })
            text = path.read_text(encoding='utf-8')
            self.assertIn(f'OPENROUTER_API_KEY={secret}', text)
            self.assertIn('AI_TIMEOUT_SECONDS=45', text)
            self.assertIn('VOICE_ENGLISH=en-IN-NeerjaNeural', text)
            self.assertNotIn('must-not-overwrite', text)
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_packaged_config_path_is_per_user_not_program_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fake_paths = ProductPaths(
                install_dir=base / 'Program Files' / 'JARVIS AI OMEGA',
                data_dir=base / 'LocalAppData' / 'JARVIS AI OMEGA',
                config_dir=base / 'LocalAppData' / 'JARVIS AI OMEGA' / 'config',
                log_dir=base / 'LocalAppData' / 'JARVIS AI OMEGA' / 'logs',
                crash_dir=base / 'LocalAppData' / 'JARVIS AI OMEGA' / 'crash-reports',
                export_dir=base / 'LocalAppData' / 'JARVIS AI OMEGA' / 'exports',
            )
            with patch('jarvis.product_paths.PATHS', fake_paths), patch.object(sys, 'frozen', True, create=True):
                path = config_env_path()
            self.assertEqual(path, fake_paths.config_dir / '.env')
            self.assertNotEqual(path.parent, fake_paths.install_dir)

    def test_local_fallback_is_reported_but_does_not_fake_primary_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text(
                'AI_PROVIDER=openrouter\nENABLE_LOCAL_FALLBACK=true\nLOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1\nLOCAL_AI_MODEL=qwen\n',
                encoding='utf-8',
            )
            state = inspect_bootstrap_state(path, environ={})
            self.assertTrue(state.local_fallback_configured)
            self.assertFalse(state.ready)


if __name__ == '__main__':
    unittest.main()
