"""Real Windows UIA against a disposable WinForms application; no mocked adapter."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from jarvis.agent.tool_runtime import RecordingToolRegistry
from jarvis.agent.verification import VerificationEngine
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.security.audit import AuditStore


class RealWindowsSemanticTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, 'nt', 'This acceptance suite requires real Windows.')
        self.title = 'JARVIS UIA Fixture ' + uuid.uuid4().hex[:10]
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        self.process = subprocess.Popen([str(shell), '-NoProfile', '-STA', '-File',
                                         str(Path(__file__).with_name('uia_fixture.ps1')), '-WindowTitle', self.title])
        self.addCleanup(self.stop)
        from pywinauto import Desktop
        self.window = Desktop(backend='uia').window(title=self.title)
        self.window.wait('visible', timeout=15)
        self.engine = ComputerActionEngine()

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=5)

    def inspect(self, label='Draft'):
        result = self.engine.inspect_target(label, window_hint=self.title)
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['actionable'], result)
        target = result['target']
        self.assertEqual(target['process_id'], self.process.pid)
        return {'observation_id': result['observation_id'], 'app': target['application'],
                'window_title': target['window_title'], 'target': target['name']}

    def test_literal_unicode_replacement_and_single_use_on_real_edit(self):
        args = self.inspect()
        result = self.engine.act_observed('type', **args, text='नमस्ते {ENTER} JARVIS')
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['verification']['verified'], result)
        self.assertEqual(self.window.child_window(auto_id='Draft', control_type='Edit').get_value(), 'नमस्ते {ENTER} JARVIS')
        self.assertFalse(self.engine.act_observed('type', **args, text='replay')['ok'])

    def test_real_invoke_changes_fixture_but_engine_keeps_workflow_unknown(self):
        result = self.engine.act_observed('click', **self.inspect('Apply'))
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['verification']['verified'])
        self.window.child_window(title='Applied', control_type='Text').wait('visible', timeout=3)

    def test_password_hidden_and_closed_application_stale(self):
        protected = self.engine.inspect_target('Password', window_hint=self.title)
        self.assertFalse(protected.get('actionable', False), protected)
        self.assertNotIn('private-password-fixture', json.dumps(protected))
        args = self.inspect()
        self.stop()
        self.assertFalse(self.engine.act_observed('type', **args, text='unsafe')['ok'])

    def test_real_uia_through_permission_audit_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'state.db'
            registry = RecordingToolRegistry(MemoryStore(db), confirmer=lambda *_: 'allow_once', audit_store=AuditStore(db))
            registry.computer = self.engine
            configured = replace(settings, enable_local_tools=True, enable_desktop_automation=True, enable_semantic_computer_use=True)
            with patch('jarvis.tools.settings', configured):
                observed = json.loads(registry.call('inspect_computer_target', {'target': 'Draft', 'window_hint': self.title}))
                self.assertTrue(observed['ok'], observed)
                value = observed['result']; target = value['target']
                registry.clear_events()
                output = json.loads(registry.call('semantic_type', {'observation_id': value['observation_id'],
                    'app': target['application'], 'window_title': target['window_title'], 'target': target['name'], 'text': 'updated by registry'}))
                self.assertTrue(output['ok'], output)
                events = registry.drain_events()
                self.assertTrue(events[0]['audit_id'])
                self.assertTrue(VerificationEngine().verify_step('updated field', events).verified)
