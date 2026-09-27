"""Regression proofs for the 2026-09-27 audit (no physical actions/network)."""
import io
import json
import queue
import tempfile
import threading
import time
import unittest
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.agent.budget import CURRENT, BudgetExceeded, ExecutionBudget, bounded_request, checked_timeout
from jarvis.agent.verification import VerificationEngine
from jarvis.config import settings
from jarvis.documents import DocumentReader, _bounded_parse
from jarvis.local_files import LocalFiles
from jarvis.readiness import ReleaseReadinessCertifier
from jarvis.wake_service import PartialWakeDetector, BackgroundWakeListener


class VerificationRepairs(unittest.TestCase):
    def test_all_windows_requests_are_effects_without_invented_observation(self):
        from jarvis.windows_controls import WINDOWS_CONTROL_ACTIONS
        for action in WINDOWS_CONTROL_ACTIONS:
            event = {'name': 'windows_control', 'output': {'ok': True, 'result': {'action': action, 'status': 'REQUESTED', 'verified': False}}}
            result = VerificationEngine().verify_tool_event(event)
            self.assertTrue(result['side_effecting'])
            self.assertFalse(result['verified'])
            self.assertTrue(VerificationEngine.has_unsafe_retry_risk([event]))

    def test_unknown_tool_cannot_self_certify(self):
        event = {'name': 'invented_tool', 'output': {'ok': True, 'verification': {'verified': True, 'status': 'VERIFIED'}}}
        self.assertEqual(VerificationEngine().verify_tool_event(event)['status'], 'UNKNOWN')
        self.assertTrue(VerificationEngine.has_unsafe_retry_risk([event]))

    def test_desired_media_commands_are_distinct_from_toggles(self):
        from jarvis.fast_commands import parse_windows_command
        for phrase, action in [('mute', 'volume_mute'), ('unmute', 'volume_unmute'), ('pause music', 'media_pause'), ('resume music', 'media_play')]:
            self.assertEqual(parse_windows_command(phrase), ('windows_control', {'action': action}))
        from jarvis.windows_controls import windows_control
        with patch('jarvis.windows_controls.os.name', 'nt'), patch('jarvis.windows_audio.set_mute', return_value=True) as mute, patch('jarvis.windows_controls._pyautogui') as pg:
            for _ in range(2):
                self.assertTrue(windows_control('volume_mute')['verified'])
            self.assertEqual(mute.call_args_list[0].args, (True,))
            self.assertEqual(mute.call_args_list[1].args, (True,))
            pg.assert_not_called()


class DocumentRepairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = LocalFiles()
        self.files.roots = (self.root.resolve(),)
        self.reader = DocumentReader(self.files)

    def test_document_and_text_routes_enforce_same_input_ceiling(self):
        path = self.root / 'large.txt'
        path.write_bytes(b'a' * 2_100_000)
        for read in (self.files.read_text, self.reader.extract):
            with self.assertRaisesRegex(ValueError, '2 MB'):
                read(str(path), max_chars=2000)

    def test_compressed_expansion_is_checked_before_parser(self):
        path = self.root / 'bomb.docx'
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('word/document.xml', b'a' * 1_000_000)
        with patch('jarvis.documents._bounded_parse') as parse:
            with self.assertRaisesRegex(ValueError, 'compressed'):
                self.reader.extract(str(path))
            parse.assert_not_called()

    def test_valid_office_document_uses_bounded_child(self):
        from docx import Document
        path = self.root / 'normal.docx'
        doc = Document()
        doc.add_paragraph('A bounded document with useful content.')
        doc.save(path)
        self.assertIn('useful content', self.reader.extract(str(path))['text'])

    def test_parser_deadline_terminates_child(self):
        with self.assertRaises((TimeoutError, ValueError, EOFError)):
            _bounded_parse(b'not a pdf', '.pdf', 2000, timeout=0.00001)

    def test_symlink_does_not_reopen_a_different_file(self):
        path, link = self.root / 'normal.txt', self.root / 'link.txt'
        path.write_text('hello')
        try:
            link.symlink_to(path)
        except OSError:
            self.skipTest('Symlink creation is unavailable to this Windows test user.')
        with self.assertRaises(PermissionError):
            self.reader.extract(str(link))


class WakeRepairs(unittest.TestCase):
    def controller(self):
        from jarvis.background_ui import BackgroundController
        desktop = MagicMock()
        desktop._closing = False
        desktop.busy = False
        desktop.voice.state = 'idle'
        desktop.wake_listener.running = False
        desktop._live_listening = desktop._live_voice_enabled = False
        with patch('jarvis.background_ui.load_preferences', return_value={}):
            controller = BackgroundController(desktop)
        controller.listener = MagicMock()
        controller.listener.ready = False
        return controller, desktop

    def test_partial_wake_does_not_consume_later_inline_command(self):
        now = [0.0]
        detector = PartialWakeDetector('jarvis', lambda: now[0])
        detector.feed('wake up jarvis')
        now[0] = .5
        self.assertEqual(detector.feed('wake up jarvis'), '')
        self.assertEqual(detector.feed('wake up jarvis open chrome', final=True), 'open chrome')

    def test_stalled_native_read_is_cancelled_and_stream_aborted(self):
        from jarvis.microphone import record_until_silence
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        stream = MagicMock()
        def read(_frames):
            entered.set()
            release.wait(2)
            return b'\0\0' * 480, False
        stream.read.side_effect = read
        stream.abort.side_effect = release.set
        context = MagicMock()
        context.__enter__.return_value = stream
        result = []
        with patch('jarvis.microphone._deps', return_value=(MagicMock(), None)), patch('jarvis.microphone._exclusive_stream', return_value=context):
            thread = threading.Thread(target=lambda: result.append(record_until_silence(stop_event=stop)))
            thread.start()
            self.assertTrue(entered.wait(1))
            stop.set()
            thread.join(1)
            release.set()
            self.assertFalse(thread.is_alive())
            self.assertEqual(result, [''])
            stream.abort.assert_called_once()

    def test_startup_does_not_block_ui_and_stale_ready_is_ignored(self):
        controller, desktop = self.controller()
        release = threading.Event()
        controller.listener.start.side_effect = lambda: release.wait(2)
        with patch.object(controller, 'ensure_tray'), patch('jarvis.background_ui.save_preferences'), patch('jarvis.background_ui.settings', replace(settings, enable_mic_input=True)):
            started = time.monotonic()
            self.assertTrue(controller.enable())
            self.assertLess(time.monotonic() - started, .5)
            controller.disable(save=False)
            release.set()
            controller.startup_thread.join(1)
            controller.poll()
        self.assertFalse(controller.enabled)
        self.assertFalse(any('microphone READY' in str(call.args) for call in desktop._append.call_args_list))

    def test_followup_thread_is_covered_by_watchdog(self):
        controller, desktop = self.controller()
        controller.enabled = controller.pending = True
        controller.preferences['enabled'] = True
        controller.followup_thread = MagicMock()
        controller.followup_thread.is_alive.return_value = True
        controller.followup_started_at = time.monotonic() - 46
        controller.poll()
        self.assertTrue(controller.followup_stop.is_set())
        self.assertFalse(controller.enabled)
        desktop.root.deiconify.assert_not_called()


class HealthRoutingBudgetRepairs(unittest.TestCase):
    def test_workspace_is_not_reported_as_execution_sandbox(self):
        from jarvis.observability.health import JarvisHealthSystem, HealthStatus
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.observability.health.ROOT', Path(folder)):
            report = JarvisHealthSystem(Path(folder) / 'state.db').run()
        checks = {item.name: item for item in report.checks}
        self.assertIn('Workspace storage', checks)
        self.assertEqual(checks['Execution isolation'].status, HealthStatus.BLOCKED)
        self.assertNotEqual(checks['Self Development'].status, HealthStatus.PASS)

    def test_low_ml_confidence_cannot_be_overridden_by_neural_agreement(self):
        from jarvis.intelligence import FiveLayerIntelligence, SemanticPrediction
        from jarvis.providers.router import ModelRouter
        config = replace(settings, adaptive_ml_min_confidence=.72, neural_routing_min_confidence=.76)
        semantic = MagicMock()
        semantic.predict.return_value = SemanticPrediction('SMART', .99, {'SMART': .99})
        semantic.status.return_value = {'available': True}
        with tempfile.TemporaryDirectory() as folder:
            stack = FiveLayerIntelligence(config=config, router=ModelRouter(config), model_path=Path(folder) / 'ml.json', semantic_router=semantic)
            with patch.object(stack.ml, 'predict', return_value=SimpleNamespace(category='SMART', confidence=.20, learned_observations=0)):
                self.assertEqual(stack.decide('hello').category, 'FAST')

    def test_boolean_stale_and_wrong_commit_evidence_fail_closed(self):
        cert = ReleaseReadinessCertifier()
        self.assertEqual(cert._evidence_status({'a': True}, 'a')[0], 'NOT_VERIFIED')
        evidence = {'ok': True, 'commit': 'a' * 40, 'artifact_sha256': 'b' * 64, 'platform': 'Windows', 'test_id': 'smoke', 'checked_at': datetime.now(timezone.utc).isoformat(), 'evidence_uri': 'ci://run/123'}
        with patch('jarvis.readiness.subprocess.run', return_value=SimpleNamespace(stdout='c' * 40)):
            self.assertEqual(cert._evidence_status({'a': evidence}, 'a')[0], 'NOT_VERIFIED')
        with patch('jarvis.readiness.subprocess.run', return_value=SimpleNamespace(stdout='a' * 40)):
            self.assertEqual(cert._evidence_status({'a': evidence}, 'a')[0], 'PASS')
        evidence['checked_at'] = '2020-01-01T00:00:00Z'
        self.assertEqual(cert._evidence_status({'a': evidence}, 'a')[0], 'NOT_VERIFIED')

    def test_budget_shared_across_nested_calls_and_cancellation(self):
        budget = ExecutionBudget(max_model_calls=1)
        token = CURRENT.set(budget)
        try:
            @bounded_request
            def model_call():
                return checked_timeout(1000)
            self.assertLessEqual(model_call(), 120)
            with self.assertRaises(BudgetExceeded):
                model_call()
            budget.cancel_event.set()
            with self.assertRaises(BudgetExceeded):
                budget.tool()
        finally:
            CURRENT.reset(token)

    def test_generated_changes_cannot_rewrite_transitive_trust_paths(self):
        from jarvis.self_development.policies import SelfDevelopmentPolicy
        policy = SelfDevelopmentPolicy()
        for path in ['jarvis/tools.py', 'jarvis/agent/verification.py', 'jarvis/readiness.py', 'server/billing.py', 'main.py', 'desktop_app.py', 'jarvis/core_v7.py', 'jarvis/security./bypass.py', 'file.txt:stream']:
            self.assertFalse(policy.path_allowed(path)[0], path)

    def test_unverified_transport_success_does_not_train_routes(self):
        from jarvis.core import JarvisOmega
        core = object.__new__(JarvisOmega)
        core.intelligence = MagicMock()
        core.observability = MagicMock()
        core.session_id = 'test'
        decision = SimpleNamespace(category='SMART', model='test', confidence=.8, generation_mode='test', tool_strategy='test')
        core._record_intelligence_outcome('test request', success=True, decision=decision)
        core.intelligence.observe.assert_called_once_with('test request', 'SMART', success=False)

class RecoveryStorageRepairs(unittest.TestCase):
    def test_local_recovery_codes_are_one_use_and_revoke_sessions(self):
        from jarvis.user_profiles import ProfileStore
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.user_profiles.PBKDF2_ITERATIONS', 1000):
            store = ProfileStore(Path(folder))
            store.create('adib', 'Adib', 'old-password')
            codes = store.recovery_codes('adib', 'old-password')
            self.assertEqual(len(codes), 5)
            raw = store.accounts_path.read_text()
            self.assertTrue(all(code not in raw for code in codes))
            store.authenticate('adib', 'old-password')
            store.recover('adib', codes[0], 'replacement-password')
            self.assertIsNone(store.resume_session())
            with self.assertRaises(PermissionError):
                store.authenticate('adib', 'old-password')
            with self.assertRaises(PermissionError):
                store.recover('adib', codes[0], 'another-password')
            self.assertEqual(store.authenticate('adib', 'replacement-password').display_name, 'Adib')

    def test_windows_dpapi_round_trip_when_available(self):
        import os
        if os.name != 'nt':
            self.skipTest('Real Windows DPAPI is verified by the Windows regression job.')
        from jarvis.local_secrets import protect, reveal
        value = 'test-only-random-session-token'
        protected = protect(value)
        self.assertNotIn(value, protected)
        self.assertTrue(protected.startswith('dpapi:v1:'))
        self.assertEqual(reveal(protected), value)

    def test_background_stale_save_cannot_overwrite_new_settings(self):
        from jarvis.background_ui import save_preferences, preference_revision, load_preferences
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.background_ui.preference_path', return_value=Path(folder) / 'prefs.json'):
            old = preference_revision()
            save_preferences({'enabled': True})
            with self.assertRaisesRegex(RuntimeError, 'changed elsewhere'):
                save_preferences({'enabled': False}, expected_revision=old)
            self.assertTrue(load_preferences()['enabled'])

    def test_file_lock_serializes_independent_store_objects(self):
        from jarvis.file_mutex import locked_file
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state'
            entered = threading.Event()
            def contender():
                with locked_file(path):
                    entered.set()
            with locked_file(path):
                thread = threading.Thread(target=contender)
                thread.start()
                self.assertFalse(entered.wait(.1))
            thread.join(1)
            self.assertTrue(entered.is_set())

    def test_crashed_effect_cannot_repeat_until_observed_resolution(self):
        from jarvis.agent.effects import EffectLedger
        from jarvis.storage.sqlite_utils import connect_sqlite
        with tempfile.TemporaryDirectory() as folder:
            ledger = EffectLedger(Path(folder) / 'state.db')
            intent = ledger.begin('open_app', {'app': 'chrome'})
            with connect_sqlite(ledger.path) as db:
                db.execute('UPDATE action_intents SET pid=99999999 WHERE id=?', (intent,))
            restarted = EffectLedger(ledger.path)
            with self.assertRaisesRegex(RuntimeError, 'UNCERTAIN_PRIOR_ACTION'):
                restarted.begin('open_app', {'app': 'chrome'})
            self.assertEqual(restarted.unresolved()[0]['state'], 'UNCERTAIN')
            restarted.resolve(intent, 'observed_applied')
            next_id = restarted.begin('open_app', {'app': 'chrome'})
            self.assertNotEqual(intent, next_id)
            restarted.finish(next_id, 'ACKNOWLEDGED')
            self.assertFalse(restarted.unresolved())

    def test_active_mission_owner_is_not_stolen(self):
        from jarvis.agent.effects import EffectLedger
        with tempfile.TemporaryDirectory() as folder:
            a = EffectLedger(Path(folder) / 'state.db')
            b = EffectLedger(a.path)
            a.claim_mission('first')
            with self.assertRaisesRegex(RuntimeError, 'MISSION_BUSY'):
                b.claim_mission('second')
            b.release_mission()
            a.check_owner()
            a.release_mission()
            b.claim_mission('second')
            b.release_mission()

    def test_saved_online_name_is_opt_in_and_never_merges_local_history(self):
        from jarvis import subscription_client
        client = SimpleNamespace(_token='opaque', display_name='Soni', use_online_name=True, expires_at=time.time()+60)
        with patch.object(subscription_client, '_active_client', client):
            self.assertEqual(subscription_client.greeting_name('Adib'), 'Soni')
            client.use_online_name = False
            self.assertEqual(subscription_client.greeting_name('Adib'), 'Adib')
            client.use_online_name = True
            client.expires_at = 0
            self.assertEqual(subscription_client.greeting_name('Adib'), 'Adib')
