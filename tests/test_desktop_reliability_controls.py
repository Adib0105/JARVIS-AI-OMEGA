from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from jarvis.runtime_guard import _read_test_output_tail, run_adaptive_gui


class DesktopReliabilityControlTests(unittest.TestCase):
    def test_adaptive_desktop_keeps_tool_failures_from_sticking_busy_state(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn('def _run_tool_async', source)
        self.assertIn("{'ok': False, 'error':", source)
        self.assertIn('self._tool_done(name, r)', source)
        self.assertIn('self._set_busy(False)', source)

    def test_ctrl_o_is_bound_to_root_entry_and_chat(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn("for widget in (self.root, self.entry, self.chat)", source)
        self.assertIn("widget.bind('<Control-o>', self._upload_shortcut)", source)
        self.assertIn("return 'break'", source)
        self.assertIn('parent=self.root', source)

    def test_image_help_is_an_interactive_image_center(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn('IMAGE CENTER', source)
        self.assertIn("'UPLOAD IMAGE'", source)
        self.assertIn("'PASTE IMAGE'", source)
        self.assertIn("'SCREEN VISION'", source)

    def test_quick_diagnose_is_non_network_desktop_feature(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn("'QUICK DIAGNOSE'", source)
        self.assertIn("name='jarvis-quick-diagnose'", source)
        self.assertIn("'sounddevice'", source)
        self.assertIn("'speech_recognition'", source)
        self.assertIn('Physical microphone/speaker quality is NOT VERIFIED', source)

    def test_code_tests_are_popen_polled_instead_of_waited_inside_tk_process(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn('def _code_tests', source)
        self.assertIn("permissions.check('run_project_tests'", source)
        self.assertIn('prepare_unit_tests(folder, timeout)', source)
        self.assertIn('subprocess.Popen(', source)
        self.assertIn('self.root.after(120, self._poll_code_test_process)', source)
        self.assertIn('def _poll_code_test_process', source)
        self.assertIn("getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)", source)
        self.assertIn('stdout=output_handle', source)
        self.assertIn("self._request_code_test_stop('TIMED OUT')", source)

    def test_cancel_button_terminates_active_code_test_tree(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn("['taskkill.exe', '/PID', str(process.pid), '/T', '/F']", source)
        self.assertIn("self._request_code_test_stop('CANCELLED')", source)
        self.assertIn('CANCELLING CODE TESTS', source)

    def test_test_log_tail_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'tests.log'
            path.write_text('x' * 100000 + '\nFINAL-LINE\n', encoding='utf-8')
            tail = _read_test_output_tail(path, max_bytes=4096, max_chars=2000)
            self.assertLessEqual(len(tail), 2000)
            self.assertIn('FINAL-LINE', tail)
            self.assertNotEqual(len(tail), 100000)


if __name__ == '__main__':
    unittest.main()
