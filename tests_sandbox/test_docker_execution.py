"""Real-container acceptance; no mocks, no skip when explicitly invoked in CI.

Requires a provisioned Linux Docker daemon and an immutable approved image ID.
Use a disposable CI/VM host, never a production daemon for these attack fixtures.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

from jarvis.code_execution import DockerCodeRunner, ExecutionControl
from jarvis.coding_tools import CodingWorkspace
from jarvis.local_files import LocalFiles
from jarvis.self_development.tester import SelfDevelopmentTester
from jarvis.agent.tool_runtime import RecordingToolRegistry
from jarvis.agent.verification import VerificationEngine
from jarvis.memory import MemoryStore
from jarvis.security.audit import AuditStore


class RealSandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        (self.root / 'tests').mkdir(parents=True)
        self.runner = DockerCodeRunner()
        self.events = []

    def source(self, body):
        (self.root / 'tests/test_case.py').write_text(body, encoding='utf-8')

    def run_code(self, **kwargs):
        result = self.runner.run(self.root, control=ExecutionControl(emit=self.events.append), timeout=kwargs.pop('timeout', 25), **kwargs)
        self.assertTrue(result['cleanup_verified'], result)
        return result

    def test_normal_workspace_and_self_development_paths_execute_in_isolation(self):
        self.source("import unittest\nclass Test(unittest.TestCase):\n def test_good(self): self.assertEqual(2+2,4)\n")
        files = LocalFiles(); files.roots = (self.root,)
        result = CodingWorkspace(files).run_unit_tests(str(self.root))
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['cleanup_verified'])
        report = SelfDevelopmentTester().run_regression(self.root)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual([x.name for x in report.checks], ['compileall', 'unittest'])

    def test_normal_tool_permission_audit_and_verification_path(self):
        self.source("import unittest\nprint('PRIVATE-FIXTURE-OUTPUT')\nclass Test(unittest.TestCase):\n def test_ready(self): self.assertEqual(3*3,9)\n")
        store = Path(self.tmp.name) / 'state.db'
        registry = RecordingToolRegistry(MemoryStore(store), confirmer=lambda *_: 'deny', audit_store=AuditStore(store))
        registry.coding.files.roots = (self.root,)
        args = {'project_dir': str(self.root), 'timeout': 25}
        denied = json.loads(registry.call('run_project_tests', args))
        self.assertFalse(denied['ok'])
        registry.clear_events()
        registry.permissions.confirmer = lambda *_: 'allow_once'
        result = json.loads(registry.call('run_project_tests', args))
        self.assertTrue(result['ok'], result)
        events = registry.drain_events()
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]['audit_id'])
        self.assertNotIn('PRIVATE-FIXTURE-OUTPUT', json.dumps(events))
        self.assertTrue(VerificationEngine().verify_step('tests passed', events).verified)

    def test_host_files_env_network_and_write_boundaries(self):
        marker = Path(self.tmp.name) / 'host-private.txt'
        marker.write_text('private')
        (self.root / '.env').write_text('PASSWORD=private')
        os.environ['JARVIS_SANDBOX_TEST_SECRET'] = 'never-forward-this'
        self.addCleanup(os.environ.pop, 'JARVIS_SANDBOX_TEST_SECRET', None)
        self.source('import os, pathlib, socket, unittest\n'
                    'class Test(unittest.TestCase):\n'
                    ' def test_boundary(self):\n'
                    f'  self.assertFalse(pathlib.Path({str(marker)!r}).exists())\n'
                    '  self.assertFalse(pathlib.Path(".env").exists())\n'
                    '  self.assertNotIn("JARVIS_SANDBOX_TEST_SECRET", os.environ)\n'
                    '  self.assertFalse(pathlib.Path("/var/run/docker.sock").exists())\n'
                    '  self.assertEqual(os.getuid(),65534)\n'
                    '  with self.assertRaises(OSError): pathlib.Path("/escape").write_text("bad")\n'
                    '  with self.assertRaises(OSError): socket.create_connection(("1.1.1.1",443),timeout=.2)\n'
                    '  pathlib.Path("local.py").write_text("only inside tmpfs")\n')
        result = self.run_code()
        self.assertTrue(result['ok'], result)
        self.assertEqual(marker.read_text(), 'private')
        self.assertFalse((self.root / 'local.py').exists())

    def test_nonzero_exit_separates_stdout_and_stderr(self):
        self.source("import sys, unittest\nprint('OUTPUT-MARKER',flush=True)\nprint('ERROR-MARKER',file=sys.stderr,flush=True)\nclass Test(unittest.TestCase):\n def test_bad(self): self.fail('expected fixture failure')\n")
        result = self.run_code()
        self.assertFalse(result['ok'])
        self.assertEqual(result['returncode'], 1)
        self.assertIn('OUTPUT-MARKER', result['stdout'])
        self.assertNotIn('ERROR-MARKER', result['stdout'])
        self.assertIn('ERROR-MARKER', result['stderr'])

    def test_timeout_and_detached_child_are_removed(self):
        self.source("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c','import time; time.sleep(300)'],start_new_session=True)\nprint('CHILD-STARTED',flush=True)\ntime.sleep(300)\n")
        start = time.monotonic()
        result = self.run_code(timeout=5)
        self.assertEqual(result['status'], 'TIMEOUT', result)
        self.assertLess(time.monotonic()-start, 16)
        self.assertTrue(any('CHILD-STARTED' in x['text'] for x in self.events))
        self.assert_no_containers()

    def test_cancellation_after_live_output_allows_next_run(self):
        self.source("import time\nprint('CANCEL-READY',flush=True)\ntime.sleep(300)\n")
        control = ExecutionControl()
        def receive(event):
            if 'CANCEL-READY' in event['text']:
                control.cancel.set()
        control.emit = receive
        result = self.runner.run(self.root, control=control, timeout=20)
        self.assertEqual(result['status'], 'CANCELLED', result)
        self.assertTrue(result['cleanup_verified'])
        self.source('import unittest\nclass Test(unittest.TestCase):\n def test_ready(self): self.assertEqual(3*3,9)\n')
        result = self.run_code()
        self.assertTrue(result['ok'], result)
        self.assert_no_containers()

    def test_empty_suite_does_not_count_as_passed(self):
        self.source('import unittest\n')
        result = self.run_code()
        self.assertFalse(result['ok'], result)

    def test_output_flood_is_killed_and_bounded(self):
        self.source("import sys\nwhile True: sys.stdout.write('x'*4096)\n")
        result = self.run_code()
        self.assertEqual(result['status'], 'OUTPUT_LIMIT', result)
        self.assertLessEqual(len(result['stdout'])+len(result['stderr']), 65536)
        self.assert_no_containers()

    def test_enforced_cgroup_and_seccomp_policy_inside_container(self):
        self.source('import pathlib,unittest\n'
                    'class Test(unittest.TestCase):\n'
                    ' def test_limits(self):\n'
                    '  root=pathlib.Path("/sys/fs/cgroup")\n'
                    '  self.assertEqual((root/"memory.max").read_text().strip(),"536870912")\n'
                    '  self.assertEqual((root/"pids.max").read_text().strip(),"64")\n'
                    '  quota,period=map(int,(root/"cpu.max").read_text().split())\n'
                    '  self.assertEqual(quota,period)\n'
                    '  status=pathlib.Path("/proc/self/status").read_text()\n'
                    '  self.assertIn("NoNewPrivs:\\t1",status)\n'
                    '  self.assertIn("Seccomp:\\t2",status)\n'
                    '  self.assertIn("CapEff:\\t0000000000000000",status)\n')
        self.assertTrue((result := self.run_code())['ok'], result)

    def test_memory_exhaustion_is_bounded(self):
        self.source("a=[]\nwhile True: a.append(bytearray(16*1024*1024))\n")
        result = self.run_code()
        self.assertFalse(result['ok'], result)
        self.assertIn(result['status'], ('MEMORY_LIMIT', 'FAILED'))
        self.assert_no_containers()

    def assert_no_containers(self):
        result = subprocess.run(['docker', '--host', 'unix:///var/run/docker.sock', 'ps', '-aq',
                                 '--filter', 'label=com.jarvis.code-sandbox=1'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '', 'A sandbox container survived cleanup.')


if __name__ == '__main__':
    unittest.main()
