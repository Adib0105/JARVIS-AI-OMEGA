from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.accounts import AccountStore, UserProfile, activate_profile_environment
from jarvis.microphone import WakeWordListener
from jarvis.system_tools import APP_URIS


ROOT = Path(__file__).resolve().parents[1]


class AccountStoreTests(unittest.TestCase):
    def test_create_authenticate_and_reject_wrong_password(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'accounts.db'
            store = AccountStore(db)
            created = store.create('amit01', 'Amit Kumar', 'StrongPass123')
            self.assertEqual(created.display_name, 'Amit Kumar')
            self.assertIsNone(store.authenticate('amit01', 'wrong-password'))
            logged_in = store.authenticate('amit01', 'StrongPass123')
            self.assertIsNotNone(logged_in)
            self.assertEqual(logged_in.display_name, 'Amit Kumar')

    def test_password_is_not_stored_as_plaintext(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'accounts.db'
            store = AccountStore(db)
            password = 'NeverStoreThisPlain123!'
            store.create('secureuser', 'Secure User', password)
            raw = db.read_bytes()
            self.assertNotIn(password.encode('utf-8'), raw)

    def test_duplicate_username_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            store = AccountStore(Path(td) / 'accounts.db')
            store.create('sameuser', 'First User', 'abcdef123')
            with self.assertRaises(ValueError):
                store.create('sameuser', 'Second User', 'abcdef456')

    def test_profile_environment_is_user_specific(self):
        profile = UserProfile(42, 'amit42', 'Amit')
        before = dict(os.environ)
        try:
            activate_profile_environment(profile)
            self.assertEqual(os.environ['USER_NAME'], 'Amit')
            self.assertEqual(os.environ['JARVIS_PROFILE_ID'], '42')
            self.assertIn(str(Path('profiles') / '42'), os.environ['JARVIS_DB_PATH'])
            self.assertTrue(os.environ['JARVIS_DB_PATH'].endswith('jarvis.db'))
        finally:
            os.environ.clear()
            os.environ.update(before)


class BackgroundWakeTests(unittest.TestCase):
    def test_wake_aliases_cover_requested_phrases(self):
        listener = WakeWordListener(lambda _command: None)
        woke, command = listener._command_from_heard('wake up jarvis open chrome')
        self.assertTrue(woke)
        self.assertEqual(command, 'open chrome')
        woke2, command2 = listener._command_from_heard('hey jervis volume badhao')
        self.assertTrue(woke2)
        self.assertEqual(command2, 'volume badhao')

    def test_wake_callback_contract_exists(self):
        listener = WakeWordListener(lambda _command: None)
        calls = []
        listener.on_wake = lambda: calls.append('wake')
        listener.on_wake()
        self.assertEqual(calls, ['wake'])


class ProductContractTests(unittest.TestCase):
    def test_windows_settings_destinations_are_allowlisted(self):
        self.assertEqual(APP_URIS['settings'], 'ms-settings:')
        self.assertEqual(APP_URIS['bluetooth settings'], 'ms-settings:bluetooth')
        self.assertEqual(APP_URIS['wifi settings'], 'ms-settings:network-wifi')
        self.assertEqual(APP_URIS['windows update'], 'ms-settings:windowsupdate')

    def test_installer_registers_background_startup_and_cleanup(self):
        text = (ROOT / 'installer' / 'JarvisOmega.iss').read_text(encoding='utf-8')
        self.assertIn('Software\\Microsoft\\Windows\\CurrentVersion\\Run', text)
        self.assertIn('--background', text)
        self.assertIn('uninsdeletevalue', text)

    def test_desktop_account_gate_precedes_runtime_import(self):
        text = (ROOT / 'desktop_app.py').read_text(encoding='utf-8')
        account_index = text.index('from jarvis.accounts import run_account_gate')
        runtime_index = text.index('from jarvis.runtime_guard import run_adaptive_gui')
        self.assertLess(account_index, runtime_index)
        self.assertIn('run_adaptive_gui(background=background)', text)

    def test_prompt_personalizes_user_but_keeps_creator_identity(self):
        text = (ROOT / 'jarvis' / 'prompt.py').read_text(encoding='utf-8')
        self.assertIn('currently signed-in local user is {settings.user_name}', text)
        self.assertIn('Mujhe {settings.creator_name} ne banaya hai.', text)
        self.assertIn('Each local account has its own memory/database namespace', text)
        self.assertIn('Never claim a message was sent merely because text was typed', text)

    def test_background_mode_does_not_auto_allow_typing_or_clicking(self):
        text = (ROOT / 'jarvis' / 'runtime_guard.py').read_text(encoding='utf-8')
        safe_block = text[text.index('background_safe = {'):text.index('if self.background_mode and tool in background_safe')]
        self.assertNotIn("'semantic_click'", safe_block)
        self.assertNotIn("'semantic_type'", safe_block)
        self.assertNotIn("'type_text'", safe_block)
        self.assertIn("'open_app'", safe_block)
        self.assertIn("'press_key'", safe_block)


if __name__ == '__main__':
    unittest.main()
