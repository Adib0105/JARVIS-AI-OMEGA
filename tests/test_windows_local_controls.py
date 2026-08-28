from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from jarvis import automation, system_tools
from jarvis.prompt import system_prompt


class WindowsAppDiscoveryTests(unittest.TestCase):
    def test_resolve_executable_prefers_path(self):
        expected = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        with patch('jarvis.system_tools.shutil.which', return_value=expected):
            self.assertEqual(system_tools._resolve_executable('chrome.exe'), expected)

    def test_resolve_executable_falls_back_to_registry(self):
        expected = r'C:\Users\test\AppData\Local\Google\Chrome\Application\chrome.exe'
        with (
            patch('jarvis.system_tools.shutil.which', return_value=None),
            patch('jarvis.system_tools._registry_app_path', return_value=expected),
            patch('jarvis.system_tools._common_windows_app_path') as common,
        ):
            self.assertEqual(system_tools._resolve_executable('chrome.exe'), expected)
            common.assert_not_called()

    def test_resolve_executable_falls_back_to_common_install_location(self):
        expected = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        with (
            patch('jarvis.system_tools.shutil.which', return_value=None),
            patch('jarvis.system_tools._registry_app_path', return_value=None),
            patch('jarvis.system_tools._common_windows_app_path', return_value=expected),
        ):
            self.assertEqual(system_tools._resolve_executable('chrome.exe'), expected)

    def test_open_app_launches_resolved_absolute_command_without_shell(self):
        expected = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        with (
            patch.object(system_tools.os, 'name', 'nt'),
            patch('jarvis.system_tools._resolve_app_command', return_value=[expected]),
            patch('jarvis.system_tools.subprocess.Popen') as popen,
        ):
            result = system_tools.open_app('chrome')
        popen.assert_called_once_with([expected], shell=False)
        self.assertEqual(result, 'Opened chrome.')

    def test_google_chrome_alias_is_allowlisted(self):
        with patch('jarvis.system_tools._resolve_executable', return_value='chrome.exe'):
            self.assertEqual(system_tools._resolve_app_command('google chrome'), ['chrome.exe'])


class WindowsVolumeControlTests(unittest.TestCase):
    def test_volume_up_is_allowlisted(self):
        pg = Mock()
        with patch('jarvis.automation._pyautogui', return_value=pg):
            result = automation.press_key('volumeup')
        pg.press.assert_called_once_with('volumeup')
        self.assertEqual(result, 'Pressed volumeup.')

    def test_volume_down_is_allowlisted(self):
        pg = Mock()
        with patch('jarvis.automation._pyautogui', return_value=pg):
            automation.press_key('volumedown')
        pg.press.assert_called_once_with('volumedown')

    def test_volume_mute_is_allowlisted(self):
        pg = Mock()
        with patch('jarvis.automation._pyautogui', return_value=pg):
            automation.press_key('volumemute')
        pg.press.assert_called_once_with('volumemute')

    def test_prompt_teaches_model_exact_volume_key_mapping(self):
        prompt = system_prompt()
        self.assertIn('volumeup', prompt)
        self.assertIn('volumedown', prompt)
        self.assertIn('volumemute', prompt)


if __name__ == '__main__':
    unittest.main()
