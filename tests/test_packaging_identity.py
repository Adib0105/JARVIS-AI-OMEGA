from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingIdentityTests(unittest.TestCase):
    def test_pyinstaller_uses_stable_binary_name(self):
        source = (ROOT / 'build_windows.ps1').read_text(encoding='utf-8')
        self.assertIn("$ProductBinaryName = 'JARVIS-OMEGA'", source)
        self.assertIn("'--name', $ProductBinaryName", source)
        self.assertIn('"$ProductBinaryName.exe"', source)

    def test_installer_uses_stable_binary_name_and_folder(self):
        source = (ROOT / 'installer' / 'JarvisOmega.iss').read_text(encoding='utf-8')
        self.assertIn('#define MyAppExeName "JARVIS-OMEGA.exe"', source)
        self.assertIn('Source: "..\\dist\\JARVIS-OMEGA\\*"', source)
        # Historical binary names may appear only as explicit upgrade-cleanup targets;
        # they must never become the canonical executable identity or package source.
        self.assertNotIn('#define MyAppExeName "JARVIS-OMEGA-V7.exe"', source)
        self.assertNotIn('Source: "..\\dist\\JARVIS-OMEGA-V7\\*"', source)
        self.assertNotIn('Filename: "{app}\\JARVIS-OMEGA-V7.exe"', source)

    def test_ci_validates_stable_binary_identity(self):
        source = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
        self.assertIn('JARVIS-OMEGA\\JARVIS-OMEGA.exe', source)
        # CI is allowed to seed an obsolete filename for repair/upgrade validation,
        # but build/run paths must continue to target only the stable product name.
        self.assertNotIn('dist\\JARVIS-OMEGA-V7\\', source)
        self.assertNotIn('dist/JARVIS-OMEGA-V7/', source)
        self.assertNotIn('.\\dist\\JARVIS-OMEGA-V7.exe', source)

    def test_installer_builder_requires_stable_executable(self):
        source = (ROOT / 'build_installer.ps1').read_text(encoding='utf-8')
        self.assertIn("$ProductBinaryName = 'JARVIS-OMEGA'", source)
        self.assertNotIn('V7 executable is missing', source)


if __name__ == '__main__':
    unittest.main()
