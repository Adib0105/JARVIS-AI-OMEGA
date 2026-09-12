import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.hud import ArcReactorHUD
from jarvis.runtime_guard import local_identity_answer
from jarvis.prompt import system_prompt
from jarvis.desktop_smoke import schedule_smoke_check


class FridayDesktopTests(unittest.TestCase):
    def test_persona_and_app_identity(self):
        self.assertIn('Friday', local_identity_answer('what is your name'))
        self.assertIn('JARVIS', local_identity_answer('tumhara naam'))
        self.assertIn('Friday', system_prompt())

    def test_stop_cancels_animation_timer(self):
        hud = MagicMock()
        hud._timer = 'timer-123'
        ArcReactorHUD.stop(hud)
        hud.after_cancel.assert_called_once_with('timer-123')
        self.assertFalse(hud._running)
        self.assertIsNone(hud._timer)

    def test_hidden_avatar_does_not_redraw(self):
        hud = MagicMock()
        hud._running = True
        hud.winfo_viewable.return_value = False
        ArcReactorHUD._animate(hud)
        hud.delete.assert_not_called()
        hud.after.assert_called_once_with(250, hud._animate)

    def test_failed_desktop_smoke_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            root, app = MagicMock(), MagicMock()
            app.hud.find_all.return_value = ()
            with patch('jarvis.desktop_smoke.report_path', return_value=path):
                schedule_smoke_check(root, app)
            root.after.call_args.args[1]()
            self.assertFalse(json.loads(path.read_text())['ok'])
            app._exit_completely.assert_called_once()

    def test_real_core_boots_without_credentials_and_reads_bom_env(self):
        # Full public core, not a mocked provider-only test; no outbound calls.
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / '.env').write_text('AI_PROVIDER=openrouter\nOPENROUTER_API_KEY=\nENABLE_VOICE_OUTPUT=false\nENABLE_MIC_INPUT=false\n', encoding='utf-8-sig')
            env = dict(os.environ, JARVIS_DB_PATH=str(home / 'test.db'))
            code = '''import sys
from pathlib import Path
sys.frozen = True
sys.executable = str(Path(sys.argv[1]) / 'JARVIS-OMEGA-V7.exe')
from jarvis.config import settings
assert settings.provider == 'openrouter' and settings.api_key == ''
from jarvis.core import JarvisOmega
app = JarvisOmega()
assert app.memory.get_session(app.session_id)
print('core-ready')
'''
            result = subprocess.run([sys.executable, '-c', code, folder], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('core-ready', result.stdout)
