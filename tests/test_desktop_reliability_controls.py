from __future__ import annotations

import inspect
import unittest

from jarvis.runtime_guard import run_adaptive_gui


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


if __name__ == '__main__':
    unittest.main()
