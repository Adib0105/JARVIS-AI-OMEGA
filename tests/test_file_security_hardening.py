from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jarvis.local_files as local_files_module
from jarvis.local_files import LocalFiles


class FileSecurityHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'allowed'
        self.outside = Path(self.temp.name) / 'outside'
        self.root.mkdir()
        self.outside.mkdir()
        self.settings_patch = patch.object(
            local_files_module,
            'settings',
            SimpleNamespace(allowed_file_roots=(self.root,)),
        )
        self.settings_patch.start()
        self.files = LocalFiles()

    def tearDown(self):
        self.settings_patch.stop()
        self.temp.cleanup()

    def test_normal_allowed_file(self):
        target = self.root / 'notes.txt'
        target.write_text('ordinary project notes', encoding='utf-8')
        self.assertEqual(self.files.read_text(str(target)), 'ordinary project notes')

    def test_parent_traversal_outside_root_is_blocked(self):
        target = self.outside / 'outside.txt'
        target.write_text('outside', encoding='utf-8')
        traversal = self.root / '..' / 'outside' / 'outside.txt'
        with self.assertRaises(PermissionError):
            self.files.read_text(str(traversal))

    def test_absolute_path_outside_root_is_blocked(self):
        target = self.outside / 'outside.txt'
        target.write_text('outside', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(target.resolve()))

    def test_symlink_escape_is_blocked(self):
        outside_file = self.outside / 'outside.txt'
        outside_file.write_text('outside', encoding='utf-8')
        link = self.root / 'linked.txt'
        try:
            link.symlink_to(outside_file)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'symlink unavailable: {exc}')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(link))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_windows_junction_escape_is_blocked(self):
        junction = self.root / 'junction'
        completed = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(junction), str(self.outside)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.skipTest('junction creation unavailable on this Windows runner')
        target = self.outside / 'outside.txt'
        target.write_text('outside', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(junction / 'outside.txt'))

    def test_renamed_secret_content_is_blocked(self):
        target = self.root / 'ordinary-notes.txt'
        target.write_text('api_key = "sk-proj-abcdefghijklmnopqrstuv"', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(target))

    def test_nested_secret_directory_is_blocked(self):
        nested = self.root / 'project' / 'secrets'
        nested.mkdir(parents=True)
        target = nested / 'notes.txt'
        target.write_text('ordinary text', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(target))

    def test_sensitive_extension_is_blocked(self):
        target = self.root / 'renamed.pem'
        target.write_text('ordinary text', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.files.read_text(str(target))


if __name__ == '__main__':
    unittest.main()
