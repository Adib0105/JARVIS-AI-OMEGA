from __future__ import annotations

import os
import unittest
from unittest import mock

from jarvis import global_hotkeys


class GlobalHotkeyContractTests(unittest.TestCase):
    def test_hotkey_ids_are_distinct(self):
        self.assertNotEqual(global_hotkeys.HOTKEY_JARVIS_ID, global_hotkeys.HOTKEY_EMOJI_ID)

    def test_non_windows_hotkeys_fail_closed(self):
        with mock.patch.object(global_hotkeys.os, 'name', 'posix'):
            self.assertFalse(global_hotkeys.show_jarvis_window())
            self.assertFalse(global_hotkeys.open_windows_emoji_panel())
            stop = global_hotkeys.start_global_hotkeys()
            self.assertFalse(stop.is_set())
            stop.set()
            self.assertTrue(stop.is_set())

    def test_source_contract_uses_ctrl_alt_j_and_ctrl_alt_e(self):
        self.assertEqual(global_hotkeys.MOD_CONTROL | global_hotkeys.MOD_ALT, 0x0003)
        self.assertEqual(global_hotkeys.VK_J, 0x4A)
        self.assertEqual(global_hotkeys.VK_E, 0x45)


if __name__ == '__main__':
    unittest.main()
