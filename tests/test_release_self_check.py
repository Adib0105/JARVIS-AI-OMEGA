from __future__ import annotations

import unittest
from pathlib import Path

from jarvis.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class ReleaseSelfCheckTests(unittest.TestCase):
    def test_canonical_self_check_uses_app_version(self):
        source = (ROOT / 'self_check_release.py').read_text(encoding='utf-8')
        self.assertIn('from jarvis.version import APP_VERSION', source)
        self.assertNotIn("JARVIS AI OMEGA V7.5 // ENGINEERING SELF CHECK", source)
        self.assertIn("'app_version': APP_VERSION", source)

    def test_self_checks_enforce_python_311_minimum(self):
        for name in ('self_check.py', 'self_check_release.py'):
            source = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('MINIMUM_PYTHON = (3, 11)', source, name)
            self.assertNotIn('sys.version_info >= (3, 10)', source, name)

    def test_release_self_check_labels_module_import_as_module_check(self):
        source = (ROOT / 'self_check_release.py').read_text(encoding='utf-8')
        self.assertIn('Controlled release + skill modules', source)
        self.assertNotIn('Controlled release + skill gates', source)

    def test_historical_self_check_is_wrapper_only(self):
        source = (ROOT / 'self_check_v75.py').read_text(encoding='utf-8')
        self.assertIn('from self_check_release import main', source)
        self.assertNotIn('ReleaseReadinessCertifier', source)

    def test_readme_identifies_current_release(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn(APP_VERSION, readme)


if __name__ == '__main__':
    unittest.main()
