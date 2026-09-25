"""Adversarial regressions: synthetic data only, no live accounts or network."""
import dataclasses
import json
import logging
import os
import socket
import subprocess
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from jarvis.agent.mission import Mission, MissionStatus
from jarvis.agent.mission_store import ConcurrentMissionUpdateError, MissionStore
from jarvis.agent.orchestrator import MissionOrchestrator
from jarvis.agent.verification import VerificationEngine
from jarvis.coding_tools import CodingWorkspace
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.browser_security import assess_public_url, resolve_public_addresses
from jarvis.config import settings
from jarvis.core_v7 import JarvisOmega
from jarvis.local_files import LocalFiles
from jarvis.logging_utils import JsonFormatter
from jarvis.memory import MemoryStore
from jarvis.retrieval import HybridRetriever
from jarvis.runtime_guard import _repair_answer
from jarvis.security.policy import CapabilityPermissionGate
from jarvis.security.redaction import redact_text
from jarvis.self_development.policies import SelfDevelopmentPolicy
from jarvis.self_development.tester import SelfDevelopmentTester
from jarvis.storage.migrations import SchemaMigrator
from jarvis.tools import ToolRegistry

SECRETS = ('sk-test-123456789', 'Bearer SUPER_SECRET_TOKEN', 'password=SuperSecret123')


class FinalHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_logging_first_import_has_no_security_cycle(self):
        result = subprocess.run(
            [sys.executable, '-c',
             'from jarvis.logging_utils import redact_text; '
             'from jarvis.security import AuditStore; '
             'assert redact_text("password=secret") == "password=[REDACTED]"; '
             'assert AuditStore.__name__ == "AuditStore"'],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_execution_fails_closed_for_all_attack_categories(self):
        attacks = {
            'env': "open('../.env').read()",
            'outside': "open('/etc/passwd').read()",
            'ssh': "open('/home/user/.ssh/id_rsa').read()",
            'secrets': "import os; print(os.environ)",
            'network': "import socket; socket.create_connection(('example.com',443))",
            'escape': "open('../escaped','w').write('x')",
            'children': "import subprocess; subprocess.Popen(['python','-c','while True: pass'])",
            'timeout': "while True: pass",
            'flood': "while True: print('x'*1000000)",
        }
        (self.root / 'tests').mkdir()
        for category, source in attacks.items():
            with self.subTest(category=category), patch('subprocess.run') as run, patch('subprocess.Popen') as popen:
                (self.root / 'tests/test_attack.py').write_text(source)
                report = SelfDevelopmentTester().run_regression(self.root)
                self.assertFalse(report.ok)
                self.assertTrue(all(x.returncode == 126 for x in report.checks))
                self.assertIn('EXECUTION_ISOLATION_UNAVAILABLE', report.checks[0].stderr)
                run.assert_not_called()
                popen.assert_not_called()

    def test_project_tests_cannot_bypass_isolation(self):
        (self.root / 'tests').mkdir()
        files = LocalFiles(); files.roots = (self.root,)
        with patch('subprocess.run') as run:
            with self.assertRaisesRegex(PermissionError, 'ISOLATION_UNAVAILABLE'):
                CodingWorkspace(files).run_unit_tests(str(self.root))
            run.assert_not_called()

    def test_trusted_mode_does_not_approve_test_execution(self):
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'true'}):
            self.assertFalse(CapabilityPermissionGate().check('run_project_tests', {}).allowed)

    def test_test_code_has_side_effect_retry_risk(self):
        self.assertTrue(VerificationEngine.has_unsafe_retry_risk([{'name': 'run_project_tests'}]))

    def test_control_plane_paths_are_immutable(self):
        for path in ('.github/workflows/ci.yml', 'jarvis/self_development/tester.py',
                     'jarvis/self_development/release.py', 'jarvis/logging_utils.py',
                     'tests/test_v7_security.py', 'tests/test_final_hardening.py'):
            self.assertFalse(SelfDevelopmentPolicy().path_allowed(path)[0], path)

    def test_no_tool_success_claim_is_unknown(self):
        result = VerificationEngine().verify_step('The email was sent successfully.', [])
        self.assertFalse(result.verified)
        self.assertEqual(result.status, 'UNKNOWN')

    def test_unchanged_focus_is_not_outcome_verification(self):
        observed = {'focused': True, 'exists': True}
        result = ComputerActionEngine._verify_click(observed, observed, observed)
        self.assertFalse(result['verified'])
        self.assertEqual(result['status'], 'UNKNOWN')

    def test_coding_kind_is_not_changed_to_planning(self):
        fake = SimpleNamespace(provider=SimpleNamespace(name='fake', structured_output=Mock(return_value='ok')),
                               _select_model=Mock(return_value='coding-model'))
        JarvisOmega._one_shot_text(fake, 'system', 'edit this file', 'coding')
        fake._select_model.assert_called_once_with('edit this file', 'coding')

    def test_rag_relevant_irrelevant_and_empty(self):
        rows = [{'content': 'apple banana recipe', 'source': 'food.md', 'confidence': .9}]
        retriever = HybridRetriever()
        self.assertEqual(retriever.rank('banana', rows)[0]['source'], 'food.md')
        self.assertEqual(retriever.rank('quantum elephant zzz', rows), [])
        self.assertEqual(retriever.rank('quantum', []), [])

    def test_response_repair_preserves_evidence_and_uncertainty(self):
        answer = 'FAILED: tool timed out. Outcome UNKNOWN. [source](https://example.com). No retry.'
        fake = SimpleNamespace(provider=Mock())
        self.assertEqual(_repair_answer(fake, 'do task', answer), answer)
        fake.provider.chat.assert_not_called()

    def test_synthetic_secrets_absent_from_chat_summary_and_database(self):
        db = self.root / 'data.db'; memory = MemoryStore(db)
        session = memory.new_session(' '.join(SECRETS))
        memory.add_message(session, 'user', ' '.join(SECRETS))
        memory.set_session_summary(session, ' '.join(SECRETS))
        content = json.dumps(memory.session_messages(session)) + memory.get_session_summary(session)
        for secret in SECRETS:
            self.assertNotIn(secret, content)
            self.assertNotIn(secret.encode(), db.read_bytes())

    def test_synthetic_secrets_absent_from_mission_state_and_events(self):
        db = self.root / 'mission.db'; store = MissionStore(db)
        mission = Mission(' '.join(SECRETS), 'session')
        mission.final_report = ' '.join(SECRETS)
        store.save_with_event(mission, 'test', {'detail': ' '.join(SECRETS)})
        for secret in SECRETS:
            self.assertNotIn(secret.encode(), db.read_bytes())

    def test_synthetic_secrets_absent_from_formatted_logs(self):
        record = logging.LogRecord('test', logging.ERROR, __file__, 0, ' '.join(SECRETS), (), None)
        rendered = JsonFormatter().format(record)
        for secret in SECRETS:
            self.assertNotIn(secret, rendered)
        self.assertIn('[REDACTED]', redact_text('cookie=abc123'))

    def test_wal_backup_contains_latest_committed_data(self):
        db = self.root / 'wal.db'
        connection = sqlite3.connect(db)
        self.addCleanup(connection.close)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE committed(value TEXT)')
        connection.execute("INSERT INTO committed VALUES ('latest')")
        connection.commit()
        backup = SchemaMigrator(db)._backup_legacy_once()
        with sqlite3.connect(backup) as restored:
            self.assertEqual(restored.execute('SELECT value FROM committed').fetchone()[0], 'latest')
            self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        restored.close()

    def test_stale_mission_snapshot_is_rejected(self):
        store = MissionStore(self.root / 'mission.db'); mission = Mission('goal', 'session')
        store.save(mission)
        stale = store.get(mission.id)
        store.save(mission)
        with self.assertRaises(ConcurrentMissionUpdateError):
            store.save(stale)

    def test_failed_event_insert_rolls_back_state_and_revision(self):
        db = self.root / 'mission.db'; store = MissionStore(db); mission = Mission('old', 's')
        store.save(mission); old_revision = mission.revision
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TRIGGER reject_event BEFORE INSERT ON v7_mission_events BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
        conn.close(); mission.goal = 'new'
        with self.assertRaises(sqlite3.IntegrityError):
            store.save_with_event(mission, 'test')
        self.assertEqual(store.get(mission.id).goal, 'old')
        self.assertEqual(mission.revision, old_revision)

    def test_initial_persistence_failure_releases_core_ownership(self):
        store = Mock()
        store.save_with_event.side_effect = sqlite3.OperationalError('injected')
        orchestrator = MissionOrchestrator(SimpleNamespace(session_id='s'), store)
        with self.assertRaises(sqlite3.OperationalError):
            orchestrator.run('goal')
        self.assertIsNone(orchestrator.current_mission_id)
        self.assertEqual(orchestrator._controls, {})

    def test_active_core_rejects_second_mission(self):
        core = SimpleNamespace(session_id='s')
        orchestrator = MissionOrchestrator(core, MissionStore(self.root / 'm.db'))
        orchestrator.current_mission_id = 'already-running'
        with self.assertRaisesRegex(RuntimeError, 'MISSION_BUSY'):
            orchestrator.run('second')

    def test_disabled_tools_do_not_reach_permission_or_handler(self):
        memory = MemoryStore(self.root / 'm.db')
        gate = Mock()
        registry = ToolRegistry(memory, permission_checker=gate)
        disabled = dataclasses.replace(settings, enable_public_web_tools=False,
                                       enable_coding_tools=False, enable_google_workspace=False)
        with patch('jarvis.tools.settings', disabled):
            for name in ('read_web_page', 'run_project_tests', 'gmail_send', 'unknown_alias'):
                self.assertIn('CAPABILITY_DISABLED', registry.call(name, {}))
        gate.check.assert_not_called()

    def test_private_dns_and_mixed_answers_fail_closed(self):
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        private = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))
        for addresses in ([private], [public, private]):
            with patch('socket.getaddrinfo', return_value=addresses):
                with self.assertRaises(ValueError):
                    resolve_public_addresses('example.com', 443)

    def test_private_url_forms_are_blocked(self):
        for url in ('http://localhost', 'http://127.0.0.1', 'http://[::1]',
                    'http://[fc00::1]', 'http://[::ffff:127.0.0.1]', 'file:///etc/passwd'):
            self.assertFalse(assess_public_url(url).allowed, url)

    def test_redirect_to_private_never_reaches_second_request(self):
        from jarvis.web_tools import read_web_page
        public = (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))
        with patch('socket.getaddrinfo', return_value=[public]), patch(
            'jarvis.web_tools._request_once', return_value=(302, {'location': 'https://127.0.0.1'}, b'')
        ) as request:
            with self.assertRaises(ValueError):
                read_web_page('https://example.com')
            self.assertEqual(request.call_count, 1)

    def test_reader_caps_huge_and_binary_files(self):
        files = LocalFiles(); files.roots = (self.root,)
        tiny = self.root / 'tiny.txt'; tiny.write_text('hello')
        self.assertEqual(files.read_text(str(tiny)), 'hello')
        huge = self.root / 'huge.txt'
        with huge.open('wb') as f:
            f.truncate(2_000_001)
        with self.assertRaises(ValueError):
            files.read_text(str(huge))
        binary = self.root / 'binary.txt'; binary.write_bytes(b'a\0b')
        with self.assertRaises(ValueError):
            files.read_text(str(binary))
        malformed = self.root / 'malformed.txt'; malformed.write_bytes(b'hello\xff')
        self.assertIn('hello', files.read_text(str(malformed)))


if __name__ == '__main__':
    unittest.main()
