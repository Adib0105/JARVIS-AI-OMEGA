from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis import updater


class AutoUpdaterContracts(unittest.TestCase):
    def test_checksum_parser_matches_installer(self):
        name = 'JARVIS-AI-OMEGA-Setup-8.0.1.exe'
        digest = 'a' * 64
        self.assertEqual(updater._expected_sha256(f'{digest}  {name}\n', name), digest)

    def test_checksum_parser_rejects_missing_installer(self):
        with self.assertRaises(RuntimeError):
            updater._expected_sha256(('b' * 64) + '  other.exe\n', 'JARVIS-AI-OMEGA-Setup-8.0.1.exe')

    def test_download_refuses_release_without_checksum(self):
        release = {'installer': {'name': 'JARVIS-AI-OMEGA-Setup-8.0.1.exe', 'url': 'https://example.invalid/setup.exe', 'size': 10}}
        with self.assertRaisesRegex(RuntimeError, 'SHA256'):
            updater.download_update(release)

    def test_download_verifies_size_and_hash(self):
        name = 'JARVIS-AI-OMEGA-Setup-8.0.1.exe'
        payload = b'verified-installer-bytes'
        digest = hashlib.sha256(payload).hexdigest()
        release = {
            'installer': {'name': name, 'url': 'https://example.invalid/setup.exe', 'size': len(payload)},
            'checksum': {'name': 'SHA256.txt', 'url': 'https://example.invalid/SHA256.txt'},
        }
        def fake_download(url, destination, **_kwargs):
            if str(url).endswith('SHA256.txt'):
                destination.write_text(f'{digest}  {name}\n', encoding='utf-8')
            else:
                destination.write_bytes(payload)
        with patch('jarvis.updater._download', side_effect=fake_download):
            path = updater.download_update(release)
        self.assertEqual(path.read_bytes(), payload)

    def test_launch_update_is_windows_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'JARVIS-AI-OMEGA-Setup-8.0.1.exe'
            path.write_bytes(b'x')
            with patch('jarvis.updater.os.name', 'posix'):
                with self.assertRaisesRegex(RuntimeError, 'Windows only'):
                    updater.launch_update(path)


if __name__ == '__main__':
    unittest.main()
