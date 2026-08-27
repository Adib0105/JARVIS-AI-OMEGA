from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_release_bundle import validate_bundle


class PackageSecurityTests(unittest.TestCase):
    def test_clean_bundle_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('JARVIS release bundle', encoding='utf-8')
            (root / '.env.example').write_text('OPENROUTER_API_KEY=put_your_key_here', encoding='utf-8')
            self.assertEqual(validate_bundle(root), [])

    def test_private_runtime_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text('OPENROUTER_API_KEY=hidden', encoding='utf-8')
            (root / 'jarvis.db').write_bytes(b'database')
            findings = validate_bundle(root)
            self.assertTrue(any('.env' in item for item in findings))
            self.assertTrue(any('jarvis.db' in item for item in findings))

    def test_secret_bytes_inside_binary_are_rejected_without_echoing_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = b'sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890'
            (root / 'JARVIS-OMEGA-V7.exe').write_bytes(b'prefix\0' + secret + b'\0suffix')
            findings = validate_bundle(root)
            self.assertEqual(len(findings), 1)
            self.assertNotIn(secret.decode(), findings[0])


if __name__ == '__main__':
    unittest.main()
