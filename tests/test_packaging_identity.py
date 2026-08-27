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
        self.assertNotIn('JARVIS-OMEGA-V7.exe', source)

    def test_ci_validates_stable_binary_identity(self):
        source = (ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
        self.assertIn('JARVIS-OMEGA\\JARVIS-OMEGA.exe', source)
        self.assertNotIn('JARVIS-OMEGA-V7', source)

    def test_installer_builder_requires_stable_executable(self):
        source = (ROOT / 'build_installer.ps1').read_text(encoding='utf-8')
        self.assertIn("$ProductBinaryName = 'JARVIS-OMEGA'", source)
        self.assertNotIn('V7 executable is missing', source)


if __name__ == '__main__':
    unittest.main()
