from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import jarvis.accounts as accounts_module
from jarvis.accounts import (
    AccountStore,
    UserProfile,
    activate_profile_environment,
    active_profile,
    clear_active_profile,
    remember_active_profile,
)
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

    def test_recovery_code_is_hashed_and_wrong_code_cannot_reset_password(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'accounts.db'
            store = AccountStore(db)
            code = 'Recovery-Only-Secret'
            store.create('recover01', 'Recover User', 'OldPassword123', code)

            self.assertNotIn(code.encode('utf-8'), db.read_bytes())
            self.assertFalse(store.reset_password('recover01', 'wrong-code', 'NewPassword123'))
            self.assertIsNotNone(store.authenticate('recover01', 'OldPassword123'))
            self.assertIsNone(store.authenticate('recover01', 'NewPassword123'))

    def test_successful_password_reset_consumes_recovery_code(self):
        with tempfile.TemporaryDirectory() as td:
            store = AccountStore(Path(td) / 'accounts.db')
            store.create('recover02', 'Recover User', 'OldPassword123', 'One-Time-Code')

            self.assertTrue(store.reset_password('recover02', 'One-Time-Code', 'NewPassword123'))
            self.assertIsNone(store.authenticate('recover02', 'OldPassword123'))
            self.assertIsNotNone(store.authenticate('recover02', 'NewPassword123'))
            self.assertFalse(store.reset_password('recover02', 'One-Time-Code', 'AnotherPassword123'))

    def test_recovery_code_rotation_and_missing_profile_are_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            store = AccountStore(Path(td) / 'accounts.db')
            profile = store.create('recover03', 'Recover User', 'OldPassword123', 'Old-Recovery')

            store.set_recovery_code(profile.id, 'New-Recovery')
            self.assertFalse(store.reset_password('recover03', 'Old-Recovery', 'NewPassword123'))
            self.assertTrue(store.reset_password('recover03', 'New-Recovery', 'NewPassword123'))
            with self.assertRaisesRegex(ValueError, 'Account not found'):
                store.set_recovery_code(999_999, 'Missing-Account')

    def test_secret_lengths_are_bounded_before_password_derivation(self):
        with tempfile.TemporaryDirectory() as td:
            store = AccountStore(Path(td) / 'accounts.db')
            profile = store.create('bounded01', 'Bounded User', 'ValidPassword123')

            self.assertIsNone(store.authenticate(profile.username, 'x' * 201))
            with self.assertRaises(ValueError):
                store.set_recovery_code(profile.id, 'x' * 201)
            with self.assertRaises(ValueError):
                store.reset_password(profile.username, 'valid-code', 'x' * 201)

    def test_legacy_schema_migrates_recovery_columns_without_losing_account(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / 'accounts.db'
            with closing(sqlite3.connect(db_path)) as db:
                db.execute('''CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TEXT
                )''')
                salt = b'0123456789abcdef'
                digest = AccountStore._derive('LegacyPassword123', salt)
                db.execute(
                    '''INSERT INTO accounts(
                        username, display_name, password_salt, password_hash
                    ) VALUES(?, ?, ?, ?)''',
                    ('legacy01', 'Legacy User', salt, digest),
                )
                db.commit()

            store = AccountStore(db_path)
            profile = store.authenticate('legacy01', 'LegacyPassword123')
            self.assertIsNotNone(profile)
            store.set_recovery_code(profile.id, 'Migrated-Code')
            self.assertTrue(store.reset_password('legacy01', 'Migrated-Code', 'NewPassword123'))

    def test_active_profile_round_trip_and_clear(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = AccountStore(root / 'accounts.db')
            profile = store.create('active01', 'Active User', 'ValidPassword123')
            active_path = root / 'active_profile.json'

            with patch.object(accounts_module, '_ACTIVE_PROFILE', active_path):
                remember_active_profile(profile)
                self.assertEqual(active_profile(store), profile)
                clear_active_profile()
                self.assertIsNone(active_profile(store))

    def test_avatar_is_square_normalized_and_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = AccountStore(root / 'accounts.db')
            profile = store.create('avatar01', 'Avatar User', 'ValidPassword123')
            source = root / 'source.png'
            Image.new('RGB', (640, 360), color=(10, 20, 30)).save(source)

            with patch.object(accounts_module, 'PATHS') as paths:
                paths.data_dir = root / 'data'
                target = store.set_avatar(profile, source)

            with Image.open(target) as avatar:
                self.assertEqual(avatar.size, (256, 256))
                self.assertEqual(avatar.format, 'PNG')
            self.assertEqual(list(target.parent.glob('.avatar-*.png')), [])


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
