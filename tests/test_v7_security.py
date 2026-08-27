import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.security.audit import AuditStore
from jarvis.security.capabilities import Capability, TOOL_SECURITY, profile_for
from jarvis.security.policy import ApprovalDecision, CapabilityPermissionGate
from jarvis.security.secrets import contains_secret, ensure_safe_for_persistent_memory


class V7SecurityTests(unittest.TestCase):
    def test_every_current_tool_name_has_profile(self):
        expected = {
            'get_system_info', 'get_system_metrics', 'get_current_time', 'remember_fact', 'recall_memory',
            'search_chat_history', 'search_knowledge', 'vector_search_knowledge', 'get_knowledge_stats',
            'add_note', 'list_notes', 'search_notes', 'get_agenda', 'add_todo', 'list_todos',
            'complete_todo', 'add_reminder', 'list_reminders', 'search_web', 'search_news', 'read_web_page',
            'browser_trust', 'browser_read_safe', 'browser_extract_safe',
            'google_status', 'gmail_search', 'gmail_send', 'calendar_upcoming', 'calendar_create',
            'list_allowed_roots', 'search_local_files', 'read_local_text_file', 'index_local_text_file',
            'read_document', 'index_document', 'open_url', 'open_app', 'open_local_path', 'browser_search',
            'computer_status', 'list_ui_targets', 'semantic_click', 'semantic_type',
            'type_text', 'press_key', 'hotkey', 'click_screen', 'list_code_tree', 'write_local_text_file',
            'run_project_tests', 'git_status', 'git_diff', 'git_log',
        }
        self.assertTrue(expected.issubset(set(TOOL_SECURITY)))
        self.assertTrue(all(profile_for(name).capabilities for name in expected))

    def test_semantic_actions_are_high_risk_and_capability_gated(self):
        click = profile_for('semantic_click')
        typed = profile_for('semantic_type')
        self.assertEqual(click.risk.value, 'HIGH')
        self.assertTrue(click.side_effecting)
        self.assertIn(Capability.SCREEN_READ, click.capabilities)
        self.assertIn(Capability.MOUSE_CONTROL, click.capabilities)
        self.assertEqual(typed.risk.value, 'HIGH')
        self.assertTrue(typed.side_effecting)
        self.assertIn(Capability.SCREEN_READ, typed.capabilities)
        self.assertIn(Capability.KEYBOARD_CONTROL, typed.capabilities)

    def test_safe_browser_reads_have_no_control_capability(self):
        for name in ('browser_trust', 'browser_read_safe', 'browser_extract_safe'):
            caps = profile_for(name).capabilities
            self.assertNotIn(Capability.BROWSER_CONTROL, caps)
            self.assertNotIn(Capability.KEYBOARD_CONTROL, caps)
            self.assertNotIn(Capability.MOUSE_CONTROL, caps)

    def test_unknown_tool_is_denied_by_default(self):
        gate = CapabilityPermissionGate(lambda *_: ApprovalDecision.ALLOW_ONCE.value)
        outcome = gate.check('unknown_dangerous_tool', {})
        self.assertFalse(outcome.allowed)
        self.assertIn('denied by default', outcome.reason)

    def test_read_capability_auto_allowed(self):
        called = []
        gate = CapabilityPermissionGate(lambda *_: called.append(True) or ApprovalDecision.DENY.value)
        outcome = gate.check('read_local_text_file', {'file_path': 'notes.txt', 'max_chars': 1000})
        self.assertTrue(outcome.allowed)
        self.assertEqual(called, [])

    def test_trusted_local_mode_auto_allows_allowlisted_app_control(self):
        called = []
        gate = CapabilityPermissionGate(lambda *_: called.append(True) or ApprovalDecision.DENY.value)
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'true', 'PERMISSION_APP_CONTROL': 'ask'}):
            outcome = gate.check('open_app', {'app': 'chrome'})
        self.assertTrue(outcome.allowed)
        self.assertEqual(called, [])
        self.assertIn('Trusted Local Mode', outcome.reason)

    def test_trusted_local_mode_auto_allows_browser_search(self):
        called = []
        gate = CapabilityPermissionGate(lambda *_: called.append(True) or ApprovalDecision.DENY.value)
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'true', 'PERMISSION_BROWSER_CONTROL': 'ask'}):
            outcome = gate.check('browser_search', {'query': 'OpenAI', 'engine': 'google'})
        self.assertTrue(outcome.allowed)
        self.assertEqual(called, [])

    def test_trusted_local_mode_does_not_bypass_high_risk_keyboard_control(self):
        calls = []
        gate = CapabilityPermissionGate(lambda *_: calls.append(1) or ApprovalDecision.ALLOW_ONCE.value)
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'true', 'PERMISSION_KEYBOARD_CONTROL': 'ask'}):
            outcome = gate.check('type_text', {'text': 'hello', 'interval': 0.02})
        self.assertTrue(outcome.allowed)
        self.assertEqual(len(calls), 1)

    def test_trusted_local_mode_does_not_bypass_semantic_keyboard_control(self):
        calls = []
        gate = CapabilityPermissionGate(lambda *_: calls.append(1) or ApprovalDecision.ALLOW_ONCE.value)
        with patch.dict(os.environ, {
            'TRUSTED_LOCAL_MODE': 'true',
            'PERMISSION_KEYBOARD_CONTROL': 'ask',
            'PERMISSION_SCREEN_READ': 'allow',
            'PERMISSION_SCREEN_CONTROL': 'ask',
        }):
            outcome = gate.check('semantic_type', {'target': 'Search', 'text': 'hello', 'window_hint': 'Chrome', 'interval': 0.02})
        self.assertTrue(outcome.allowed)
        self.assertEqual(len(calls), 1)

    def test_disabling_trusted_local_mode_restores_prompt(self):
        calls = []
        gate = CapabilityPermissionGate(lambda *_: calls.append(1) or ApprovalDecision.ALLOW_ONCE.value)
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'false', 'PERMISSION_APP_CONTROL': 'ask'}):
            outcome = gate.check('open_app', {'app': 'chrome'})
        self.assertTrue(outcome.allowed)
        self.assertEqual(len(calls), 1)

    def test_file_write_can_be_allowed_for_session(self):
        calls = []
        gate = CapabilityPermissionGate(lambda *_: calls.append(1) or ApprovalDecision.ALLOW_SESSION.value)
        with patch.dict(os.environ, {'PERMISSION_FILE_WRITE': 'ask', 'PERMISSION_CODE_WRITE': 'ask'}):
            first = gate.check('write_local_text_file', {'file_path': 'x.py', 'content': 'print(1)'})
            second = gate.check('write_local_text_file', {'file_path': 'y.py', 'content': 'print(2)'})
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertEqual(len(calls), 1)

    def test_require_local_approval_false_still_does_not_bypass_high_risk(self):
        calls = []
        gate = CapabilityPermissionGate(
            lambda *_: calls.append(1) or ApprovalDecision.ALLOW_ONCE.value,
            require_approval=False,
        )
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'false', 'PERMISSION_MOUSE_CONTROL': 'ask', 'PERMISSION_SCREEN_CONTROL': 'ask'}):
            outcome = gate.check('click_screen', {'x': 100, 'y': 100, 'button': 'left'})
        self.assertTrue(outcome.allowed)
        self.assertEqual(len(calls), 1)

    def test_email_send_always_asks_even_after_session_request(self):
        calls = []
        gate = CapabilityPermissionGate(lambda *_: calls.append(1) or ApprovalDecision.ALLOW_SESSION.value)
        with patch.dict(os.environ, {'PERMISSION_EMAIL_SEND': 'always_ask'}):
            first = gate.check('gmail_send', {'to': 'a@example.com', 'subject': 'Hi', 'body': 'Test'})
            second = gate.check('gmail_send', {'to': 'a@example.com', 'subject': 'Hi2', 'body': 'Test2'})
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertEqual(len(calls), 2)

    def test_explicit_deny_policy_wins(self):
        gate = CapabilityPermissionGate(lambda *_: ApprovalDecision.ALLOW_ONCE.value)
        with patch.dict(os.environ, {'PERMISSION_FILE_READ': 'deny'}):
            outcome = gate.check('read_local_text_file', {'file_path': 'notes.txt', 'max_chars': 1000})
        self.assertFalse(outcome.allowed)
        self.assertIn('FILE_READ', outcome.reason)

    def test_secret_detector_blocks_api_key_and_password(self):
        self.assertTrue(contains_secret('OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456'))
        self.assertTrue(contains_secret('password: super-secret-password'))
        with self.assertRaises(PermissionError):
            ensure_safe_for_persistent_memory('token=abcdefghijklmnopqrstuvwxyz123456')

    def test_secret_detector_catches_json_jwt_basic_and_url_credentials(self):
        samples = (
            '{"api_key": "a-very-secret-value"}',
            'Authorization: Basic dXNlcjpwYXNzd29yZA==',
            'eyJabcdefghijk.abcdefghijk.abcdefghijk',
            'https://user:password@example.com/private',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(contains_secret(sample))

    def test_audit_store_hashes_args_and_redacts_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            secret = 'sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890'
            audit_id = store.record(
                mission_id='MSN-1', session_id='S-1',
                request_summary=f'use api_key={secret}', tool_name='gmail_send', risk_level='HIGH',
                capabilities=[Capability.EMAIL_SEND.value], args={'api_key': secret, 'to': 'a@example.com'},
                approval_status='ALLOW_ONCE', execution_status='SUCCESS', provider='fake', model='fake-model',
            )
            rows = store.list_entries(limit=5)
            self.assertEqual(rows[0]['id'], audit_id)
            self.assertNotIn(secret, rows[0]['request_summary'])
            self.assertEqual(len(rows[0]['arguments_hash']), 64)
            # Raw argument values do not exist in the returned audit schema.
            self.assertNotIn('args', rows[0])


if __name__ == '__main__':
    unittest.main()