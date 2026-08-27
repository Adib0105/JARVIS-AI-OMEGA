from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace

from jarvis.core import JarvisOmega as PublicJarvisOmega
from jarvis.core_v7 import JarvisOmega as ProviderJarvisOmega


class _FakeOrchestrator:
    def __init__(self):
        self.calls = []

    def run(self, goal, progress=None):
        self.calls.append((goal, progress))
        return SimpleNamespace(id='mission-test', final_report='canonical report')


class MissionArchitectureTests(unittest.TestCase):
    def test_legacy_provider_entry_point_is_only_an_orchestrator_wrapper(self):
        core = object.__new__(ProviderJarvisOmega)
        core.orchestrator = _FakeOrchestrator()
        core.last_mission_id = None
        progress = lambda _message: None

        report = ProviderJarvisOmega.run_mission(core, 'goal', progress)

        self.assertEqual(report, 'canonical report')
        self.assertEqual(core.last_mission_id, 'mission-test')
        self.assertEqual(core.orchestrator.calls, [('goal', progress)])

    def test_no_duplicated_legacy_mission_loop_remains_in_provider_entry_point(self):
        source = inspect.getsource(ProviderJarvisOmega.run_mission)
        self.assertIn('self.orchestrator.run', source)
        self.assertNotIn('self.plan_mission(', source)
        self.assertNotIn('self.chat(', source)

    def test_public_and_compatibility_entry_points_both_reach_orchestrator(self):
        provider_source = inspect.getsource(ProviderJarvisOmega.run_mission)
        public_source = inspect.getsource(PublicJarvisOmega.run_mission)
        self.assertIn('self.orchestrator.run', provider_source)
        self.assertIn('self.orchestrator.run', public_source)

    def test_provider_core_uses_audited_recording_tool_runtime(self):
        init_source = inspect.getsource(ProviderJarvisOmega.__init__)
        self.assertIn('RecordingToolRegistry', init_source)
        self.assertNotIn('ToolRegistry(', init_source.replace('RecordingToolRegistry(', ''))


if __name__ == '__main__':
    unittest.main()
