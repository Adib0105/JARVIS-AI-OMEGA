import tempfile
import unittest
from pathlib import Path

from jarvis.agent.tool_runtime import RecordingToolRegistry
from jarvis.memory import MemoryStore
from jarvis.security.policy import CapabilityPermissionGate
from jarvis.tools import ToolRegistry


class DummyDecision:
    allowed = True
    reason = 'test'


class DummyPermissionChecker:
    def __init__(self):
        self.calls = []

    def check(self, name, args):
        self.calls.append((name, args))
        return DummyDecision()


class V75ArchitectureBoundaryTests(unittest.TestCase):
    def test_tool_registry_preserves_injected_permission_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / 'memory.db')
            checker = DummyPermissionChecker()
            tools = ToolRegistry(memory, permission_checker=checker)
            self.assertIs(tools.permissions, checker)
            result = tools.call('get_current_time', {})
            self.assertIn('"ok": true', result.lower())
            self.assertEqual(checker.calls[0][0], 'get_current_time')

    def test_v7_recording_registry_constructs_with_capability_gate_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / 'memory.db')
            tools = RecordingToolRegistry(memory, audit_store=None)
            self.assertIsInstance(tools.permissions, CapabilityPermissionGate)


if __name__ == '__main__':
    unittest.main()
