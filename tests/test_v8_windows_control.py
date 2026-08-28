from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from jarvis.automation import hotkey, press_key
from jarvis.computer_use.local_command_router import route_local_command
from jarvis.product_architecture import product_architecture


class V8WindowsControlTests(unittest.TestCase):
    def test_direct_chrome_command_routes_locally_through_tool_gate(self):
        calls = []

        def tool(name, args):
            calls.append((name, args))
            return json.dumps({'ok': True, 'result': 'opened'})

        result = route_local_command('chrome kholo', tool)
        self.assertTrue(result.handled)
        self.assertTrue(result.success)
        self.assertEqual(calls, [('open_app', {'app': 'chrome'})])

    def test_compound_command_is_left_for_agent_planner(self):
        result = route_local_command('chrome kholo aur youtube par SRK search karo', lambda *_: '')
        self.assertFalse(result.handled)

    def test_volume_and_media_commands_use_existing_audited_key_tool(self):
        calls = []

        def tool(name, args):
            calls.append((name, args))
            return json.dumps({'ok': True, 'result': 'pressed'})

        self.assertTrue(route_local_command('volume badhao', tool).success)
        self.assertTrue(route_local_command('music pause karo', tool).success)
        self.assertEqual(calls[0], ('press_key', {'key': 'volumeup'}))
        self.assertEqual(calls[1], ('press_key', {'key': 'playpause'}))

    @patch('jarvis.automation._pyautogui')
    def test_media_keys_are_allowlisted(self, pg_factory):
        pg = pg_factory.return_value
        press_key('playpause')
        press_key('nexttrack')
        press_key('prevtrack')
        self.assertEqual(pg.press.call_count, 3)

    @patch('jarvis.automation._pyautogui')
    def test_window_hotkeys_are_allowlisted(self, pg_factory):
        pg = pg_factory.return_value
        hotkey(['win', 'up'])
        hotkey(['win', 'down'])
        hotkey(['alt', 'f4'])
        hotkey(['win', 'tab'])
        self.assertEqual(pg.hotkey.call_count, 4)

    def test_product_manifest_has_required_home_ai_layers(self):
        manifest = product_architecture()
        names = {item['name'] for item in manifest['modules']}
        required = {'CORE', 'VOICE', 'VISION', 'COMPUTER', 'BROWSER', 'PRODUCTIVITY', 'HOME', 'OFFICE', 'DEVELOPER', 'SECURITY', 'ANALYTICS', 'COMMERCIAL'}
        self.assertTrue(required.issubset(names))
        self.assertEqual(manifest['release_gate'], {'P0': 0, 'P1': 0})


if __name__ == '__main__':
    unittest.main()
