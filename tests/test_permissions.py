import unittest

from jarvis.permissions import PermissionGate


class PermissionTests(unittest.TestCase):
    def test_safe_tool(self):
        self.assertTrue(PermissionGate().check('get_system_info', {}).allowed)

    def test_unknown_tool_blocked(self):
        self.assertFalse(PermissionGate().check('run_shell', {}).allowed)


if __name__ == '__main__':
    unittest.main()
