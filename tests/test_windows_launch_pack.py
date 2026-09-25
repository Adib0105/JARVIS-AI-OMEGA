import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.fast_commands import parse_fast_command
from jarvis.security.capabilities import profile_for
from jarvis.windows_controls import WINDOWS_CONTROL_ACTIONS, windows_control


class WindowsPowerPackTests(unittest.TestCase):
    def test_exactly_twenty_allowlisted_actions(self):
        self.assertEqual(len(WINDOWS_CONTROL_ACTIONS), 20)
        self.assertEqual(len(set(WINDOWS_CONTROL_ACTIONS)), 20)
        self.assertTrue(profile_for('windows_control').side_effecting)
        self.assertEqual(profile_for('windows_control').risk.value, 'HIGH')

    def test_media_window_and_settings_dispatch_without_shell(self):
        pg = MagicMock()
        lock = MagicMock(return_value=True)
        fake_windll = SimpleNamespace(user32=SimpleNamespace(LockWorkStation=lock))
        with (
            patch('jarvis.windows_controls.os.name', 'nt'),
            patch('jarvis.windows_controls._pyautogui', return_value=pg),
            patch('jarvis.windows_controls.os.startfile', create=True) as startfile,
            patch.object(ctypes, 'windll', fake_windll, create=True),
        ):
            for action in WINDOWS_CONTROL_ACTIONS:
                result = windows_control(action)
                self.assertEqual(result['action'], action)
                self.assertEqual(result['status'], 'REQUESTED')
        self.assertEqual(pg.press.call_count, 6)
        self.assertEqual(pg.hotkey.call_count, 8)
        self.assertEqual(startfile.call_count, 5)
        lock.assert_called_once()

    def test_unsupported_and_non_windows_fail_closed(self):
        with patch('jarvis.windows_controls.os.name', 'posix'):
            with self.assertRaisesRegex(RuntimeError, 'Windows only'):
                windows_control('volume_up')
        with patch('jarvis.windows_controls.os.name', 'nt'):
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                windows_control('run_arbitrary_shell')

    def test_voice_shortcuts_cover_power_pack(self):
        samples = {
            'volume badhao': 'volume_up',
            'Jarvis awaz kam karo': 'volume_down',
            'mute': 'volume_mute',
            'next song': 'media_next',
            'show desktop': 'show_desktop',
            'window badlo': 'switch_window',
            'current window close karo': 'close_window',
            'computer lock karo': 'lock_pc',
            'wifi settings kholo': 'open_wifi_settings',
            'bluetooth settings kholo': 'open_bluetooth_settings',
        }
        for phrase, action in samples.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_fast_command(phrase), ('windows_control', {'action': action}))


if __name__ == '__main__':
    unittest.main()
