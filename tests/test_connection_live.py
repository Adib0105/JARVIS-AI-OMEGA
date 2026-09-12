import io
import json
import os
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.config import settings
from jarvis import connection_manager as cm
from jarvis.providers.missing_credentials import MissingCredentialsProvider
from jarvis.fast_commands import execute_fast_command, parse_fast_command
from jarvis.speech_worker import play_prefetched, speech_segments


class LiveConnectionTests(unittest.TestCase):
    def test_save_immediately_authenticates_real_sdk_request_without_restart(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.headers.get('Authorization'))
                self.rfile.read(int(self.headers['Content-Length']))
                data = json.dumps({'id': 'ci', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'OK', 'tool_calls': []}, 'finish_reason': 'stop'}], 'model': 'test-model'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        core = SimpleNamespace(provider=MissingCredentialsProvider('openrouter'), observability=MagicMock(),
                               _model_observability_context=lambda: {}, session_id='keep-this-chat')
        try:
            config = replace(settings, provider='openrouter', openrouter_api_key='', openrouter_base_url=f'http://127.0.0.1:{server.server_port}/v1')
            # The fixture is loopback-only; do not route it through a workstation proxy.
            with tempfile.TemporaryDirectory() as folder, patch.object(cm, 'settings', config), patch.dict(os.environ, {'NO_PROXY': '127.0.0.1'}, clear=True):
                path = Path(folder) / '.env'
                path.write_text('# keep this comment\nUNRELATED=yes\nOPENROUTER_API_KEY=\n', encoding='utf-8-sig')
                cm.save_and_apply(core, 'openrouter', 'ci-synthetic-key', 'test-model', path)
                reply = core.provider.chat(system='test', messages=[{'role': 'user', 'content': 'test'}], model='test-model', timeout=3)
                self.assertEqual(reply.text, 'OK')
                self.assertEqual(received, ['Bearer ci-synthetic-key'])
                self.assertEqual(cm.read_connection_file(path)['UNRELATED'], 'yes')
                self.assertIn('# keep this comment', path.read_text())
                self.assertEqual(core.session_id, 'keep-this-chat')
        finally:
            cm.close_client(core.provider)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_save_failure_keeps_runtime_and_old_file(self):
        config = replace(settings, provider='openrouter', openrouter_api_key='previous')
        old, new = MagicMock(), MagicMock()
        new.name = 'openrouter'
        core = SimpleNamespace(provider=old, observability=MagicMock(), _model_observability_context=lambda: {})
        with tempfile.TemporaryDirectory() as folder, patch.object(cm, 'settings', config), patch.object(cm, 'create_primary_provider', return_value=new), patch('pathlib.Path.replace', side_effect=OSError('disk full')):
            path = Path(folder) / '.env'
            path.write_text('OPENROUTER_API_KEY=previous\n')
            with self.assertRaises(OSError):
                cm.save_and_apply(core, 'openrouter', 'new-value', path=path)
            self.assertEqual(config.openrouter_api_key, 'previous')
            self.assertIs(core.provider, old)
            self.assertEqual(path.read_text(), 'OPENROUTER_API_KEY=previous\n')
            self.assertEqual(list(Path(folder).iterdir()), [path])
        new.client.close.assert_called_once()

    def test_blank_entry_uses_saved_key_and_provider_switch_clears_old_routes(self):
        config = replace(settings, provider='openai', openrouter_api_key='', fast_model='wrong-provider-model')
        new = MagicMock()
        new.name = 'openrouter'
        core = SimpleNamespace(provider=MagicMock(), observability=MagicMock(), _model_observability_context=lambda: {})
        with tempfile.TemporaryDirectory() as folder, patch.object(cm, 'settings', config), patch.object(cm, 'create_primary_provider', return_value=new), patch.dict(os.environ):
            path = Path(folder) / '.env'
            path.write_text('OPENROUTER_API_KEY=saved-test-value\n')
            cm.save_and_apply(core, 'openrouter', path=path)
            self.assertEqual(config.openrouter_api_key, 'saved-test-value')
            self.assertEqual(config.fast_model, '')
            self.assertEqual(cm.read_connection_file(path)['FAST_MODEL'], '')

    def test_wrong_provider_and_env_assignment_rejected_without_echoing_key(self):
        for provider, value in [('openai', 'sk-or-v1-test-only'), ('openrouter', 'OPENROUTER_API_KEY=test')]:
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(cm.ConnectionInputError) as caught:
                cm.save_and_apply(MagicMock(), provider, value, path=Path(folder)/'.env')
            self.assertNotIn(value, str(caught.exception))


class VoicePipelineTests(unittest.TestCase):
    def test_next_segment_renders_during_current_playback_in_order(self):
        next_ready = threading.Event()
        heard = []
        def render(text, path):
            path.write_text(text)
            if text == 'second':
                next_ready.set()
        def play(path):
            value = path.read_text()
            heard.append(value)
            if value == 'first':
                self.assertTrue(next_ready.wait(2), 'Next audio did not render during playback')
        with tempfile.TemporaryDirectory() as folder:
            play_prefetched(['first', 'second'], folder, render, play)
            self.assertFalse(list(Path(folder).iterdir()))
        self.assertEqual(heard, ['first', 'second'])

    def test_short_prefetch_segments_preserve_all_words(self):
        text = 'Hello boss. ' + 'Yeh aapke liye ek jawab hai. ' * 100
        chunks = list(speech_segments(text))
        self.assertLessEqual(max(map(len, chunks)), 400)
        self.assertEqual(' '.join(chunks), text.strip())

    def test_screenshot_search_routes_without_ai_and_denial_is_terminal(self):
        command = 'chrome me jao youtube search kro aur hindi gana search'
        self.assertEqual(parse_fast_command(command), ('browser_search', {'engine': 'youtube', 'query': 'hindi gana'}))
        app = MagicMock()
        app.tools.call.return_value = {'ok': False, 'error': 'denied'}
        self.assertIn('complete nahi', execute_fast_command(app, command))
        app.tools.call.assert_called_once()
