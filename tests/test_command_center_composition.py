from __future__ import annotations

import inspect
import unittest

from jarvis import ui_command_center as base_ui
from jarvis.ui_command_center_composed import AgentCommandCenter
from jarvis.ui_release_extension import install_release_ui
from jarvis.ui_skill_extension import install_skill_ui


class CommandCenterCompositionTests(unittest.TestCase):
    def test_release_and_skill_installers_are_noops(self):
        build = base_ui.AgentCommandCenter._build
        install_release_ui()
        install_skill_ui()
        self.assertIs(base_ui.AgentCommandCenter._build, build)

    def test_composed_command_center_adds_release_and_skill_tabs(self):
        self.assertTrue(issubclass(AgentCommandCenter, base_ui.AgentCommandCenter))
        for name in (
            '_build_release_tab',
            '_deploy_selected_release',
            '_rollback_selected_release',
            '_build_skills_tab',
            '_prepare_skill',
            '_build_skill',
            '_activate_skill',
            '_disable_skill',
        ):
            self.assertIn(name, AgentCommandCenter.__dict__)

    def test_composed_build_calls_base_then_extensions(self):
        source = inspect.getsource(AgentCommandCenter._build)
        self.assertIn('super()._build()', source)
        self.assertIn('self._build_release_tab()', source)
        self.assertIn('self._build_skills_tab()', source)


if __name__ == '__main__':
    unittest.main()
