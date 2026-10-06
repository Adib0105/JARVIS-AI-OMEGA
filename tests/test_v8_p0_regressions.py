"""Fault regressions: real Tcl event loop/threads/SQLite; simulated hardware only."""
import json
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.agent.mission import MissionStatus
from jarvis.agent.mission_store import MissionStore
from jarvis.agent.orchestrator import MissionOrchestrator
from jarvis.agent.verification import VerificationEngine
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.targets import UITarget
from jarvis.evaluation.benchmark import AgentEvaluationBenchmark
from jarvis.gui import JarvisDesktop
from jarvis.microphone import MicrophoneUnavailable, _bounded_transcribe
from jarvis.wake_service import BackgroundWakeListener


# Retain interpreters on the test/main thread even when testing old, broken
# workers that keep their UI closure alive after a failed assertion.
_EVENT_LOOPS = []

class MainThreadLoop:
    """Real headless Tcl timers, with cross-thread Tk calls rejected explicitly."""
    def __init__(self):
        self.tk = tk.Tcl()
        _EVENT_LOOPS.append(self.tk)
        self.owner = threading.get_ident()
        self.foreign_calls = []

    def after(self, *args):
        if threading.get_ident() != self.owner:
            self.foreign_calls.append(threading.get_ident())
            raise RuntimeError('Tk called by worker')
        return self.tk.after(*args)

    def after_cancel(self, key):
        assert threading.get_ident() == self.owner
        return self.tk.after_cancel(key)

    def pump(self, condition, timeout=1.5):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.tk.eval('update')
            time.sleep(.002)
        return condition()


class DesktopJobRegressions(unittest.TestCase):
    def desktop(self, call):
        d = JarvisDesktop.__new__(JarvisDesktop)
        d.root = MainThreadLoop()
        d.jarvis = SimpleNamespace(tools=SimpleNamespace(call=call))
        d.busy, d.hud, d._closing = False, None, False
        d.output = []
        d._append = lambda kind, text: d.output.append((threading.get_ident(), kind, text))
        d._refresh_tasks = lambda: None
        def cleanup():
            tasks = getattr(d, '_tool_tasks', None)
            if tasks is not None:
                tasks.close()
        self.addCleanup(cleanup)
        return d

    def test_delayed_code_test_keeps_event_loop_alive_and_finishes_on_ui_thread(self):
        entered, release = threading.Event(), threading.Event()
        def call(*_args):
            entered.set()
            release.wait(2)
            return '{"ok": false, "error": "EXECUTION_ISOLATION_UNAVAILABLE"}'
        d = self.desktop(call)
        self.addCleanup(release.set)
        ticks = []
        def heartbeat():
            ticks.append(time.monotonic())
            if not release.is_set():
                d.root.after(5, heartbeat)
        d.root.after(0, heartbeat)
        with patch('jarvis.gui.filedialog.askdirectory', return_value='/reviewed-project'), patch('threading.excepthook'):
            start = time.monotonic()
            d._code_tests()
            self.assertLess(time.monotonic() - start, .3)
            self.assertTrue(entered.wait(.5))
            self.assertTrue(d.root.pump(lambda: len(ticks) >= 5))
            self.assertTrue(d.busy)
            release.set()
            self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertFalse(d.root.foreign_calls)
        self.assertIn('EXECUTION_ISOLATION_UNAVAILABLE', d.output[-1][2])
        self.assertEqual(d.output[-1][0], d.root.owner)

    def test_dispatch_exception_restores_busy_and_next_job_works(self):
        def crash(*_args):
            raise RuntimeError('permission or audit storage unavailable')
        d = self.desktop(crash)
        with patch('threading.excepthook'):
            d._run_tool_async('run_project_tests', {}, 'TESTING')
            self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertIn('RuntimeError', d.output[-1][2])
        d.jarvis.tools.call = lambda *_args: '{"ok": true}'
        d._run_tool_async('get_current_time', {}, 'READING')
        self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertIn('true', d.output[-1][2])

    def test_duplicate_job_is_rejected_and_closed_ui_ignores_late_result(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def call(*_args):
            calls.append(1)
            entered.set()
            release.wait(2)
            return 'late'
        d = self.desktop(call)
        self.addCleanup(release.set)
        with patch('threading.excepthook'):
            d._run_tool_async('run_project_tests', {}, 'TESTING')
            self.assertTrue(entered.wait(.5))
            d._run_tool_async('run_project_tests', {}, 'TESTING')
            d._closing = True
            release.set()
            d.root.pump(lambda: bool(d.output), timeout=.15)
        self.assertEqual(len(calls), 1)
        self.assertFalse(d.output)
        self.assertFalse(d.root.foreign_calls)

    def test_worker_exit_and_thread_start_failure_restore_ui(self):
        def exit_worker(*_args):
            raise SystemExit('worker stopped')
        d = self.desktop(exit_worker)
        d._run_tool_async('run_project_tests', {}, 'TESTING')
        self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertIn('SystemExit', d.output[-1][2])
        with patch('threading.Thread.start', side_effect=RuntimeError('thread unavailable')):
            d._run_tool_async('run_project_tests', {}, 'TESTING')
        self.assertFalse(d.busy)
        self.assertIn('thread unavailable', d.output[-1][2])

    def test_output_flood_is_bounded_for_the_tk_widget(self):
        d = self.desktop(lambda *_: 'x' * 200000)
        d._run_tool_async('run_project_tests', {}, 'TESTING')
        self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertLess(len(d.output[-1][2]), 66000)
        self.assertIn('truncated', d.output[-1][2])

    def test_command_center_error_is_delivered_on_main_thread(self):
        from jarvis.ui_command_center import AgentCommandCenter
        from jarvis.ui_tasks import TkTaskRunner
        loop = MainThreadLoop()
        runner = TkTaskRunner(loop)
        self.addCleanup(runner.close)
        view = SimpleNamespace(_task_runner=runner, overall=SimpleNamespace(configure=lambda **_: None))
        failures = []
        def crash():
            raise RuntimeError('diagnostic failed')
        with patch('jarvis.ui_command_center.messagebox.showerror', side_effect=lambda *_args, **_kwargs: failures.append(threading.get_ident())):
            AgentCommandCenter._background(view, crash)
            self.assertTrue(loop.pump(lambda: bool(failures)))
        self.assertEqual(failures, [loop.owner])
        self.assertFalse(loop.foreign_calls)


class VoiceOwnershipRegressions(unittest.TestCase):
    def test_asr_worker_exit_reports_error_and_releases_ownership(self):
        def crash(*_args):
            raise SystemExit('worker exit')
        with self.assertRaisesRegex(MicrophoneUnavailable, 'SystemExit'):
            _bounded_transcribe(crash, b'a', 16000, 'en', threading.Event())
        self.assertEqual(_bounded_transcribe(lambda *_: 'recovered', b'a', 16000, 'en', threading.Event()), 'recovered')

    def test_stalled_abort_never_blocks_stop_and_retries_share_one_abort(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def abort():
            calls.append(1)
            entered.set()
            release.wait(3)
        listener = BackgroundWakeListener('', lambda _: None, lambda _: None)
        listener._stream = SimpleNamespace(abort=abort)
        finished = threading.Event()
        caller = threading.Thread(target=lambda: (listener.stop(), finished.set()))
        caller.start()
        try:
            self.assertTrue(entered.wait(.5))
            self.assertTrue(finished.wait(.3), 'native abort blocked the caller')
            for _ in range(10):
                listener.stop()
            self.assertEqual(calls, [1])
        finally:
            release.set()
            caller.join(1)
            abort_worker = getattr(listener, '_abort_thread', None)
            if abort_worker:
                abort_worker.join(1)

    def test_cancelled_asr_keeps_ownership_until_worker_really_exits(self):
        entered, release, stopped, finished = (threading.Event() for _ in range(4))
        outcome = []
        def recognize(*_args):
            entered.set()
            release.wait(3)
            finished.set()
            return 'late result'
        caller = threading.Thread(target=lambda: outcome.append(_bounded_transcribe(recognize, b'a', 16000, 'en', stopped)))
        caller.start()
        try:
            self.assertTrue(entered.wait(.5))
            stopped.set()
            caller.join(.5)
            self.assertFalse(caller.is_alive())
            self.assertEqual(outcome, [''])
            with self.assertRaises(MicrophoneUnavailable):
                _bounded_transcribe(lambda *_: 'duplicate', b'a', 16000, 'en', threading.Event())
        finally:
            release.set()
            caller.join(1)
            finished.wait(1)
            # Wait for the actual owner thread's finally block, not an arbitrary sleep.
            for t in threading.enumerate():
                if t.name == 'jarvis-command-asr':
                    t.join(1)
        self.assertEqual(_bounded_transcribe(lambda *_: 'recovered', b'a', 16000, 'en', threading.Event()), 'recovered')


class VerificationRegressions(unittest.TestCase):
    def test_non_boolean_verified_flag_and_malformed_contract_cannot_certify(self):
        for explicit in [{'status': 'VERIFIED', 'verified': 'false'},
                         {'status': 'VERIFIED', 'verified': 1},
                         {'status': 'invented', 'verified': True}, 'VERIFIED']:
            with self.subTest(explicit=explicit):
                check = VerificationEngine().verify_tool_event({'name': 'get_current_time',
                    'output': {'ok': True, 'verification': explicit}})
                self.assertFalse(check['verified'])
                self.assertNotEqual(check['status'], 'VERIFIED')

    def test_nonexistent_todo_is_not_verified(self):
        from jarvis.memory import MemoryStore
        from jarvis.tools import ToolRegistry
        with tempfile.TemporaryDirectory() as folder:
            memory = MemoryStore(Path(folder) / 'todos.db')
            tools = ToolRegistry(memory, confirmer=lambda *_: True)
            todo = memory.add_todo('verify the actual database result')
            for uid, expected in [(99999, False), (todo['id'], True), (todo['id'], False)]:
                with self.subTest(uid=uid, expected=expected):
                    check = VerificationEngine().verify_tool_event({'name': 'complete_todo',
                        'output': tools.call('complete_todo', {'todo_id': uid})})
                    self.assertEqual(check['verified'], expected)
                    self.assertEqual(check['status'], 'VERIFIED' if expected else 'FAILED')

    def test_noop_typing_existing_substring_is_not_verified(self):
        target = UITarget('Search', 'Edit', 'Editor')
        state = {'observed': True, 'exists': True, 'focused': True, 'value': 'hello already exists'}
        backend = SimpleNamespace(enumerate_targets=lambda **_: [target],
            observe=lambda _: dict(state), focus=lambda _: dict(state))
        engine = ComputerActionEngine(backend=backend)
        with patch.dict(sys.modules, {'pyautogui': SimpleNamespace(write=lambda *_, **__: None)}):
            result = engine.semantic_type('Search', 'hello')
        self.assertFalse(result['verification']['verified'])
        self.assertNotEqual(result['verification']['status'], 'VERIFIED')

    def test_typing_requires_confirmed_focus_and_a_new_observed_value(self):
        from unittest.mock import Mock
        target = UITarget('Search', 'Edit', 'Editor')
        state = {'observed': True, 'exists': True, 'focused': False, 'value': ''}
        backend = SimpleNamespace(enumerate_targets=lambda **_: [target],
            observe=lambda _: dict(state), focus=lambda _: dict(state))
        engine = ComputerActionEngine(backend=backend)
        write = Mock(side_effect=lambda *_, **__: state.update(value='hello'))
        with patch.dict(sys.modules, {'pyautogui': SimpleNamespace(write=write)}):
            result = engine.semantic_type('Search', 'hello')
            self.assertFalse(result['ok'])
            write.assert_not_called()
            state['focused'] = True
            result = engine.semantic_type('Search', 'hello')
            self.assertTrue(result['verification']['verified'])
            self.assertEqual(result['verification']['evidence']['scope'], 'field_value_change')

    def test_verification_timeout_preserves_events_and_never_replays_side_effect(self):
        class Tools:
            events = []
            def clear_events(self): self.events = []
            def drain_events(self):
                events, self.events = self.events, []
                return events
        class Core:
            session_id, last_provider_used = 'fault-test', 'fixture'
            calls, replans = 0, 0
            def __init__(self): self.tools = Tools()
            def plan_mission(self, _): return ['Create one todo']
            def chat(self, _):
                self.calls += 1
                self.tools.events.append({'name': 'add_todo', 'output': json.dumps({'ok': True, 'result': self.calls})})
                return 'created'
            def _one_shot_text(self, *_):
                self.replans += 1
                return '["Create one todo again"]'
            def _extract_plan(self, raw, _): return json.loads(raw)
        with tempfile.TemporaryDirectory() as folder:
            core = Core()
            store = MissionStore(Path(folder) / 'mission.db')
            runner = MissionOrchestrator(core, store)
            with patch.object(runner.verifier, 'verify_step', side_effect=TimeoutError('readback timed out')), patch.object(runner.retry, 'wait', return_value=True):
                mission = runner.run('Make one todo')
            self.assertEqual(core.calls, 1)
            self.assertEqual(core.replans, 0)
            self.assertEqual(mission.retry_count, 0)
            self.assertEqual(mission.status, MissionStatus.FAILED)
            self.assertEqual(store.get(mission.id).plan[0].tool_events[0]['name'], 'add_todo')

    def test_failed_result_object_does_not_pass_benchmark(self):
        result = AgentEvaluationBenchmark.run_case('failure', 'task', lambda: {'success': False})
        self.assertFalse(result.success)

    def test_more_scenarios_alone_cannot_certify_improvement(self):
        result = AgentEvaluationBenchmark.compare({'metrics': {'scenario_count': 1.0}},
                                                   {'metrics': {'scenario_count': 100.0}})
        self.assertFalse(result['successful_improvement'])

    def test_replacing_the_scenarios_cannot_certify_improvement(self):
        before = {'results': [{'name': 'hard', 'category': 'task'}], 'metrics': {'task_success_rate': 0.0}}
        after = {'results': [{'name': 'easy', 'category': 'task'}], 'metrics': {'task_success_rate': 1.0}}
        self.assertFalse(AgentEvaluationBenchmark.compare(before, after)['successful_improvement'])

    def test_truthy_strings_do_not_certify_self_improvement(self):
        from jarvis.self_development.benchmark import SelfImprovementBenchmark
        proposal = SimpleNamespace(evaluation_summary={'benchmark_comparison': {'successful_improvement': 'false'}},
                                   test_summary={'regression': {'ok': 'false'}})
        development = SimpleNamespace(store=SimpleNamespace(get=lambda _: proposal))
        self.assertFalse(SelfImprovementBenchmark(development, None).evidence_allows_success('test'))


if __name__ == '__main__':
    unittest.main()
