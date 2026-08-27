from __future__ import annotations

import re
import unittest
from pathlib import Path

from jarvis import __version__
from jarvis.config import settings
from jarvis.version import APP_VERSION, WINDOWS_FILE_VERSION, windows_file_version


ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_runtime_version_has_one_authority(self):
        self.assertEqual(__version__, APP_VERSION)
        self.assertEqual(settings.app_version, APP_VERSION)

    def test_windows_version_is_derived_from_release_version(self):
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?', APP_VERSION)
        self.assertIsNotNone(match)
        assert match is not None
        expected = '.'.join((*match.groups()[:3], match.group(4) or '0'))
        self.assertEqual(WINDOWS_FILE_VERSION, expected)
        self.assertEqual(windows_file_version(APP_VERSION), expected)

    def test_build_and_installer_do_not_define_a_second_release_version(self):
        config = (ROOT / 'jarvis' / 'config.py').read_text(encoding='utf-8')
        package_init = (ROOT / 'jarvis' / '__init__.py').read_text(encoding='utf-8')
        installer_script = (ROOT / 'build_installer.ps1').read_text(encoding='utf-8')
        installer = (ROOT / 'installer' / 'JarvisOmega.iss').read_text(encoding='utf-8')
        workflow = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')

        self.assertNotIn(APP_VERSION, config)
        self.assertNotIn(APP_VERSION, package_init)
        self.assertNotIn(APP_VERSION, installer_script)
        self.assertNotIn(APP_VERSION, installer)
        self.assertNotIn(f'/DMyAppVersion={APP_VERSION}', workflow)
        self.assertIn('jarvis.version', installer_script)

    def test_readme_release_heading_matches_canonical_source(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        first_line = readme.splitlines()[0]
        self.assertIn(APP_VERSION, first_line)
        self.assertNotIn('V7.5', first_line)
        self.assertNotIn('7.0.0', first_line)


if __name__ == '__main__':
    unittest.main()
