from __future__ import annotations

import inspect
import unittest

from jarvis.runtime_guard import run_adaptive_gui
from jarvis.voice_ui import install_voice_ui, voice_desktop_class


class DummyDesktop:
    pass


class DummyGui:
    CYAN_DIM = '#0'
    GREEN = '#0'
    CYAN = '#0'
    RED = '#0'
    GOLD = '#0'
    MUTED = '#0'


class VoiceUICompositionTests(unittest.TestCase):
    def test_voice_installer_is_noop(self):
        before = dict(DummyDesktop.__dict__)
        self.assertIsNone(install_voice_ui())
        self.assertEqual(before, dict(DummyDesktop.__dict__))

    def test_voice_ui_is_provided_by_subclass(self):
        cls = voice_desktop_class(DummyDesktop, DummyGui)
        self.assertTrue(issubclass(cls, DummyDesktop))
        for name in ('_build_input_bar', '_voice_state_changed', '_toggle_voice', '_close'):
            self.assertIn(name, cls.__dict__)

    def test_adaptive_launcher_composes_voice_class(self):
        source = inspect.getsource(run_adaptive_gui)
        self.assertIn('voice_desktop_class', source)
        self.assertNotIn('gui_module.JarvisDesktop._confirm_tool =', source)
        self.assertNotIn('gui_module.JarvisDesktop._build_right_panel =', source)


if __name__ == '__main__':
    unittest.main()
