import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.user_profiles import ActiveProfile, ProfileStore


class UserProfileTests(unittest.TestCase):
    def test_create_authenticate_resume_and_no_plaintext_password(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            profile = store.create('Adib.01', 'Md Adib Azam', 'strong-pass-123')
            self.assertEqual(profile.username, 'adib.01')
            self.assertEqual(profile.display_name, 'Md Adib Azam')
            raw = store.accounts_path.read_text(encoding='utf-8')
            self.assertNotIn('strong-pass-123', raw)
            data = json.loads(raw)
            account = data['accounts']['adib.01']
            self.assertIn('password_digest', account)
            self.assertIn('password_salt', account)
            self.assertEqual(store.resume_session(), profile)
            store.sign_out()
            self.assertIsNone(store.resume_session())
            self.assertEqual(store.authenticate('adib.01', 'strong-pass-123'), profile)

    def test_wrong_password_and_tampered_session_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            store.create('adib', 'Adib', 'correct-password')
            with self.assertRaisesRegex(PermissionError, 'incorrect'):
                store.authenticate('adib', 'wrong-password')
            session = json.loads(store.session_path.read_text(encoding='utf-8'))
            session['token'] = 'tampered'
            store.session_path.write_text(json.dumps(session), encoding='utf-8')
            self.assertIsNone(store.resume_session())

    def test_profiles_have_separate_data_and_activate_name(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            first = store.create('first', 'First User', 'first-password', remember=False)
            second = store.create('second', 'Second User', 'second-password', remember=False)
            self.assertNotEqual(first.data_dir, second.data_dir)
            with patch.dict(os.environ, {}, clear=False):
                second.activate()
                self.assertEqual(os.environ['JARVIS_ACTIVE_DISPLAY_NAME'], 'Second User')
                self.assertEqual(Path(os.environ['JARVIS_ACTIVE_DATA_DIR']), second.data_dir)

    def test_first_profile_can_keep_existing_legacy_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / 'legacy'
            legacy.mkdir()
            (legacy / 'jarvis.db').write_bytes(b'existing')
            store = ProfileStore(root / 'auth')
            profile = store.create('owner', 'Owner', 'owner-password', legacy_data_dir=legacy)
            self.assertEqual(profile.data_dir, legacy.resolve())

    def test_input_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            with self.assertRaises(ValueError):
                store.create('x', 'Adib', 'long-enough-password')
            with self.assertRaises(ValueError):
                store.create('valid-id', 'Adib', 'short')

    def test_active_profile_name_and_data_override_legacy_env_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            active = Path(folder) / 'active'
            legacy = Path(folder) / 'legacy.db'
            env = dict(
                os.environ,
                JARVIS_ACTIVE_DATA_DIR=str(active),
                JARVIS_ACTIVE_DISPLAY_NAME='Second User',
                JARVIS_DB_PATH=str(legacy),
                USER_NAME='Wrong Legacy Name',
            )
            code = (
                'from jarvis.config import settings; '
                'assert settings.user_name == "Second User"; '
                'assert settings.db_path.name == "jarvis.db"; '
                'assert settings.db_path.parent.name == "active"'
            )
            result = subprocess.run(
                [sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=20
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
