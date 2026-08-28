import re
import unittest
from pathlib import Path

from jarvis import __version__
from jarvis.config import settings
from jarvis.version import (
    APP_VERSION,
    PRODUCT_DISPLAY_NAME,
    PRODUCT_SERIES,
    WINDOWS_ARTIFACT_BASENAME,
    WINDOWS_INSTALLER_BASENAME,
)


class VersionConsistencyTests(unittest.TestCase):
    def test_runtime_version_has_one_canonical_value(self):
        self.assertEqual(APP_VERSION, '7.5.0')
        self.assertEqual(__version__, APP_VERSION)
        self.assertEqual(settings.app_version, APP_VERSION)
        self.assertEqual(PRODUCT_SERIES, 'V7.5')
        self.assertIn(PRODUCT_SERIES, PRODUCT_DISPLAY_NAME)
        self.assertIn(PRODUCT_SERIES, WINDOWS_ARTIFACT_BASENAME)
        self.assertIn(PRODUCT_SERIES, WINDOWS_INSTALLER_BASENAME)

    def test_build_and_installer_read_canonical_python_metadata(self):
        root = Path(__file__).resolve().parents[1]
        windows = (root / 'build_windows.ps1').read_text(encoding='utf-8')
        installer_build = (root / 'build_installer.ps1').read_text(encoding='utf-8')
        installer = (root / 'installer' / 'JARVIS-OMEGA-V7.5.iss').read_text(encoding='utf-8')
        for symbol in ('APP_VERSION', 'PRODUCT_DISPLAY_NAME', 'WINDOWS_ARTIFACT_BASENAME'):
            self.assertIn(symbol, windows)
            self.assertIn(symbol, installer_build)
        self.assertIn('WINDOWS_INSTALLER_BASENAME', installer_build)
        self.assertNotRegex(installer, re.compile(r'#define\s+MyAppVersion\s+"'))
        self.assertIn('MyAppVersion must be supplied', installer)


if __name__ == '__main__':
    unittest.main()
