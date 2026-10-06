"""Execution policy, real subprocess/pipe failures and real Tcl queue regressions.

Docker control replies are simulated here. tests_sandbox exercises a real daemon.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from jarvis.agent.event_safety import sanitize_tool_output
from jarvis.agent.verification import VerificationEngine
from jarvis.code_execution import (DockerCodeRunner, ExecutionControl, _OutputLines,
                                   _UNCLEAN, snapshot_project)
from jarvis.process_runner import ProcessResult, run_process
from jarvis.ui_tasks import TkCallGate, TkTaskRunner
from test_v8_p0_regressions import MainThreadLoop
import test_v8_p0_regressions as ui_fixtures

IMAGE = 'sha256:' + 'a' * 64
ENGINE = {'OSType': 'linux', 'CgroupVersion': '2', 'MemoryLimit': True,
          'SwapLimit': True, 'PidsLimit': True, 'CpuCfsQuota': True,
          'SecurityOptions': ['name=seccomp,profile=builtin']}


class SandboxPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_pass.py').write_text('import unittest\n', encoding='utf-8')
        self.calls = []
        _UNCLEAN.clear()
        self.addCleanup(_UNCLEAN.clear)

    def fake_cli(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        args = argv[5:]
        value = b''
        if args[0] == 'info':
            value = json.dumps(ENGINE).encode()
        elif args[:2] == ['image', 'inspect']:
            value = json.dumps([{'Id': IMAGE, 'Os': 'linux', 'Config': {}}]).encode()
        elif args[0] == 'inspect':
            value = b'{"Running":false,"Status":"exited","ExitCode":0,"OOMKilled":false}'
        elif args[0] == 'start':
            # Verify the production stdin framing and snapshot, not just arguments.
            source = kwargs['stdin']
            size = int.from_bytes(source.read(8), 'big')
            data = source.read()
            self.assertEqual(size, len(data))
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                self.assertIn('tests/test_pass.py', archive.getnames())
            kwargs['on_output']('stdout', b'pass\n')
            value = b'pass\n'
        return ProcessResult(0, value, b'')

    def run_fake(self, effect=None, **kwargs):
        with patch('shutil.which', return_value=sys.executable), patch('jarvis.code_execution.run_process', side_effect=effect or self.fake_cli):
            return DockerCodeRunner(IMAGE).run(self.root, **kwargs)

    def test_unconfigured_and_mutable_images_never_spawn(self):
        for image in ('', 'python:latest', 'python@sha256:' + 'b'*64, '--privileged'):
            with self.subTest(image=image), patch('subprocess.Popen') as spawn:
                with self.assertRaisesRegex(PermissionError, 'ISOLATION_UNAVAILABLE'):
                    DockerCodeRunner(image).run(self.root)
                spawn.assert_not_called()

    def test_missing_docker_never_falls_back_to_host(self):
        with patch('shutil.which', return_value=None), patch('subprocess.Popen') as spawn:
            with self.assertRaises(PermissionError):
                DockerCodeRunner(IMAGE).run(self.root)
            spawn.assert_not_called()

    def test_each_required_engine_boundary_fails_closed(self):
        for key in ENGINE:
            info = dict(ENGINE)
            info[key] = [] if key == 'SecurityOptions' else False
            with self.subTest(key=key), self.assertRaises(PermissionError):
                DockerCodeRunner._verify_engine(info)

    def test_container_receives_no_host_mounts_network_secrets_or_mutable_image(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://evil:2375', 'DOCKER_CONTEXT': 'evil',
                                     'OPENAI_API_KEY': 'sk-fake-sensitive', 'PYTHONPATH': '/untrusted'}):
            result = self.run_fake()
        self.assertTrue(result['ok'], result)
        command = next(a for a, _ in self.calls if 'create' in a)
        for flag in ('--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges=true',
                     '--user=65534:65534', '--pids-limit=64', '--memory=512m', '--memory-swap=512m', '--cpus=1'):
            self.assertIn(flag, command)
        self.assertFalse(any(a.startswith(('--mount', '--volume', '--privileged', '--env')) for a in command))
        self.assertIn(IMAGE, command)
        for _, kwargs in self.calls:
            self.assertNotIn('DOCKER_HOST', kwargs['env'])
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('PYTHONPATH', kwargs['env'])
        self.assertTrue(result['cleanup_verified'])

    def test_image_with_implicit_volume_never_starts(self):
        def cli(argv, **kw):
            if argv[5:7] == ['image', 'inspect']:
                return ProcessResult(0, json.dumps([{'Id': IMAGE, 'Os': 'linux', 'Config': {'Volumes': {'/data': {}}}}]).encode(), b'')
            return self.fake_cli(argv, **kw)
        result = self.run_fake(cli)
        self.assertFalse(result['ok'])
        self.assertFalse(any('create' in args for args, _ in self.calls))

    def test_unknown_command_is_rejected_before_daemon_call(self):
        with self.assertRaises(ValueError):
            self.run_fake(kind='shell')
        self.assertEqual(self.calls, [])

    def test_nonzero_oom_and_uncertain_exit_never_pass(self):
        states = ({'Running': False, 'Status': 'exited', 'ExitCode': 2},
                  {'Running': False, 'Status': 'exited', 'ExitCode': 137, 'OOMKilled': True},
                  {'Running': True, 'Status': 'running', 'ExitCode': 0},
                  {'Running': False, 'Status': 'exited', 'ExitCode': False})
        for state in states:
            def cli(argv, **kw):
                if argv[5] == 'inspect':
                    return ProcessResult(0, json.dumps(state).encode(), b'')
                return self.fake_cli(argv, **kw)
            with self.subTest(state=state):
                result = self.run_fake(cli)
                self.assertFalse(result['ok'], result)
                self.assertTrue(result['cleanup_verified'])

    def test_timeout_cancel_and_flood_remove_container(self):
        for reason in ('timeout', 'cancelled', 'output_limit'):
            def cli(argv, **kw):
                if argv[5] == 'start':
                    return ProcessResult(-9, b'partial', b'problem', reason)
                return self.fake_cli(argv, **kw)
            with self.subTest(reason=reason):
                result = self.run_fake(cli)
                self.assertEqual(result['status'], reason.upper())
                self.assertTrue(result['cleanup_verified'])
                self.assertFalse(result['ok'])

    def test_old_python_empty_discovery_exit_zero_is_not_success(self):
        def cli(argv, **kw):
            if argv[5] == 'start':
                return ProcessResult(0, b'', b'Ran 0 tests in 0.00s\nOK\n')
            return self.fake_cli(argv, **kw)
        result = self.run_fake(cli)
        self.assertEqual(result['status'], 'NO_TESTS')
        self.assertFalse(result['ok'])

    def test_cleanup_failure_blocks_until_removal_confirmed(self):
        def broken(argv, **kw):
            if argv[5] in ('rm', 'container'):
                return ProcessResult(1, b'', b'daemon unavailable')
            return self.fake_cli(argv, **kw)
        first = self.run_fake(broken)
        self.assertEqual(first['status'], 'CLEANUP_FAILED')
        self.assertFalse(first['ok'])
        self.calls.clear()
        second = self.run_fake(broken)
        self.assertFalse(second['ok'])
        self.assertFalse(any('create' in args for args, _ in self.calls))
        self.assertTrue(self.run_fake()['ok'])
        self.assertFalse(_UNCLEAN)

    def test_concurrent_and_precancelled_runs_never_dispatch(self):
        from jarvis.code_execution import _LOCK
        control = ExecutionControl()
        control.cancel.set()
        with self.assertRaises(InterruptedError):
            self.run_fake(control=control)
        _LOCK.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                self.run_fake()
        finally:
            _LOCK.release()
        self.assertEqual(self.calls, [])

    def test_snapshot_excludes_credentials_git_data_and_is_independent(self):
        for name in ('.env', 'credentials.json', 'photo.png'):
            (self.root / name).write_text('private')
        for name in ('.git', 'data', '.venv'):
            (self.root / name).mkdir()
            (self.root / name / 'private.py').write_text('private')
        target = Path(self.tmp.name) / 'copy.tar'
        result = snapshot_project(self.root, target, ExecutionControl(), time.monotonic()+5)
        with tarfile.open(target) as archive:
            self.assertEqual(archive.getnames(), ['tests/test_pass.py'])
        self.assertEqual(result['files'], 1)
        self.assertEqual((self.root / '.env').read_text(), 'private')

    def test_snapshot_rejects_linked_file_including_link_outside_root(self):
        outside = Path(self.tmp.name) / 'outside.py'
        outside.write_text('private')
        linked = self.root / 'leak.py'
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation needs Windows developer mode')
        with self.assertRaises(PermissionError):
            snapshot_project(self.root, Path(self.tmp.name)/'copy.tar', ExecutionControl(), time.monotonic()+5)

    def test_snapshot_size_limit_is_enforced(self):
        (self.root / 'large.py').write_bytes(b'x' * 2_000_001)
        with self.assertRaises(ValueError):
            snapshot_project(self.root, Path(self.tmp.name)/'copy.tar', ExecutionControl(), time.monotonic()+5)

    def test_stream_redaction_handles_split_tokens_and_oversized_lines(self):
        events = []
        lines = _OutputLines(ExecutionControl(emit=events.append))
        lines.feed('stderr', b'password=Sec')
        self.assertFalse(events)
        lines.feed('stderr', b'ret123\nnormal\n')
        lines.feed('stdout', b'x'*4097)
        lines.finish()
        text = json.dumps(events)
        self.assertNotIn('Secret123', text)
        self.assertIn('[REDACTED]', text)
        self.assertIn('normal', text)
        self.assertIn('suppressed', text)

    def test_stdout_stderr_are_private_in_persisted_mission_evidence(self):
        value = sanitize_tool_output({'ok': True, 'result': {'stdout': 'private file contents', 'stderr': 'other private data'}})
        self.assertNotIn('private file contents', value)
        self.assertNotIn('other private data', value)
        self.assertIn('PRIVATE_TEXT', value)

    def test_exit_zero_without_cleanup_cannot_verify(self):
        for result in ({'returncode': 0}, {'returncode': False},
                       {'returncode': 0, 'ok': True, 'status': 'PASSED', 'cleanup_verified': False}):
            check = VerificationEngine().verify_step('done', [{'name': 'run_project_tests',
                'output': json.dumps({'ok': True, 'result': result})}])
            self.assertFalse(check.verified)


class RealProcessTests(unittest.TestCase):
    def run_python(self, source, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            return run_process([sys.executable, '-u', '-c', source], cwd=directory,
                               env=os.environ.copy(), timeout=kwargs.pop('timeout', 3), **kwargs)

    def test_stdout_stderr_and_nonzero_exit(self):
        events = []
        result = self.run_python("import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)", on_output=lambda *x: events.append(x))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b'out\n' if os.name != 'nt' else b'out\r\n')
        self.assertIn(b'err', result.stderr)
        self.assertEqual({x[0] for x in events}, {'stdout', 'stderr'})

    def test_flood_is_bounded_and_process_reaped(self):
        result = self.run_python("import sys\nwhile True: sys.stdout.write('x'*4096)", output_limit=5000)
        self.assertEqual(result.reason, 'output_limit')
        self.assertEqual(len(result.stdout) + len(result.stderr), 5000)

    def test_timeout_and_cancel_are_bounded(self):
        start = time.monotonic()
        result = self.run_python('import time; time.sleep(30)', timeout=.2)
        self.assertEqual(result.reason, 'timeout')
        event = threading.Event()
        def output(*_):
            event.set()
        result = self.run_python("import time; print('started', flush=True); time.sleep(30)", cancel=event, on_output=output)
        self.assertEqual(result.reason, 'cancelled')
        self.assertLess(time.monotonic()-start, 3)

    @unittest.skipIf(os.name == 'nt', 'Host process groups are POSIX; container tree checks run in Docker CI')
    def test_descendant_holding_pipes_cannot_hang_caller(self):
        start = time.monotonic()
        result = self.run_python("import subprocess,sys\nsubprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])", timeout=.3)
        self.assertEqual(result.reason, 'timeout')
        self.assertLess(time.monotonic()-start, 2)


class CodeUiTests(unittest.TestCase):
    def test_live_output_permission_and_cancel_use_only_tk_owner(self):
        # The real test process is test-authored fixture code, not user code.
        fixture = ui_fixtures.DesktopJobRegressions()
        self.addCleanup(fixture.doCleanups)
        from jarvis.code_execution import CURRENT
        def call(*_):
            control = CURRENT.get()
            allowed = d._ui_calls.call(lambda: True, cancel=control.cancel)
            self.assertTrue(allowed)
            result = run_process([sys.executable, '-u', '-c', "import time; print('running'); time.sleep(30)"],
                                 cwd=tempfile.gettempdir(), env=os.environ.copy(), timeout=10,
                                 cancel=control.cancel, on_output=lambda stream, data: control.event(stream, data.decode()))
            return json.dumps({'status': result.reason})
        d = fixture.desktop(call)
        d._ui_calls = TkCallGate(d.root)
        self.addCleanup(d._ui_calls.close)
        d._run_tool_async('run_project_tests', {}, 'TESTING')
        ticks = []
        def heartbeat():
            ticks.append(1)
            if d.busy:
                d.root.after(5, heartbeat)
        heartbeat()
        self.assertTrue(d.root.pump(lambda: any('running' in row[2] for row in d.output)))
        self.assertGreater(len(ticks), 2)
        d._cancel_code_tests()
        self.assertTrue(d.busy)
        self.assertTrue(d.root.pump(lambda: not d.busy))
        self.assertIn('cancelled', d.output[-1][2])
        self.assertFalse(d.root.foreign_calls)

    def test_approval_timeout_close_and_queue_saturation_deny(self):
        loop = MainThreadLoop()
        gate = TkCallGate(loop)
        self.addCleanup(gate.close)
        called, results = [], []
        worker = threading.Thread(target=lambda: results.append(gate.call(lambda: called.append(1) or True, timeout=.05)))
        worker.start(); worker.join(1)
        self.assertEqual(results, [False])
        loop.pump(lambda: gate.pending.empty())
        self.assertFalse(called)
        gate.close()
        self.assertFalse(gate.call(lambda: True))

    def test_progress_flood_drains_before_completion_and_recovers_callback_error(self):
        loop = MainThreadLoop()
        runner = TkTaskRunner(loop)
        self.addCleanup(runner.close)
        final, errors, events = [], [], []
        def work():
            for i in range(1000):
                runner.post_progress({'stream': 'stdout', 'text': str(i)})
            return 'done'
        runner.start(work, final.append, errors.append, progress=events.append)
        self.assertTrue(loop.pump(lambda: bool(final)))
        self.assertEqual(final, ['done'])
        self.assertFalse(errors)
        self.assertLessEqual(len(events), 129)
        runner.start(work, final.append, errors.append, progress=lambda _: (_ for _ in ()).throw(ValueError('display unavailable')))
        self.assertTrue(loop.pump(lambda: bool(errors)))
        self.assertFalse(runner.running)
