from __future__ import annotations

import runpy
import unittest
from pathlib import Path

from jarvis.version import APP_VERSION, WINDOWS_FILE_VERSION


ROOT = Path(__file__).resolve().parents[1]


class WindowsReleaseScriptTests(unittest.TestCase):
    def test_pyinstaller_version_resource_uses_canonical_versions(self):
        namespace = runpy.run_path(str(ROOT / 'scripts' / 'generate_windows_version_info.py'))
        rendered = namespace['render_version_info']()
        numeric = tuple(int(part) for part in WINDOWS_FILE_VERSION.split('.'))

        self.assertIn(f'filevers={numeric}', rendered)
        self.assertIn(f'prodvers={numeric}', rendered)
        self.assertIn(f"StringStruct('FileVersion', '{WINDOWS_FILE_VERSION}')", rendered)
        self.assertIn(f"StringStruct('ProductVersion', '{APP_VERSION}')", rendered)
        self.assertIn("StringStruct('OriginalFilename', 'JARVIS-OMEGA.exe')", rendered)

    def test_windows_build_embeds_and_verifies_version_resource(self):
        build = (ROOT / 'build_windows.ps1').read_text(encoding='utf-8')

        self.assertIn('generate_windows_version_info.py', build)
        self.assertIn("'--version-file', $VersionInfo", build)
        self.assertIn('WINDOWS_FILE_VERSION', build)
        self.assertIn('.VersionInfo', build)
        self.assertIn('ActualFileVersion', build)
        self.assertIn('ActualProductVersion', build)
        self.assertNotIn(f"$Version = '{APP_VERSION}'", build)

    def test_windows_setup_uses_constrained_release_environment(self):
        setup = (ROOT / 'setup_windows.ps1').read_text(encoding='utf-8')

        self.assertNotIn('V6', setup)
        self.assertNotIn('V7.5', setup)
        self.assertIn('pip==26.2.1', setup)
        self.assertGreaterEqual(setup.count('-c constraints-release.txt'), 2)
        self.assertIn('-r requirements.txt', setup)
        self.assertIn('-r requirements-windows.txt', setup)
        self.assertIn('-r requirements-build.txt', setup)
        self.assertIn('from jarvis.version import APP_VERSION', setup)
        self.assertIn('self_check.py', setup)
        self.assertNotIn('pip install --upgrade pip', setup)

    def test_launchers_do_not_hardcode_legacy_product_versions(self):
        for name in ('run_desktop.bat', 'run_jarvis.bat'):
            launcher = (ROOT / name).read_text(encoding='utf-8')
            self.assertNotIn('V6', launcher, name)
            self.assertNotIn('V7', launcher, name)
            self.assertNotIn(APP_VERSION, launcher, name)
            self.assertIn('JARVIS AI OMEGA', launcher, name)

    def test_release_docs_use_current_stable_binary_path(self):
        for relative in ('docs/V7-SETUP.md', 'docs/V7-TESTING.md', 'docs/V7-RELEASE.md'):
            document = (ROOT / relative).read_text(encoding='utf-8')
            self.assertNotIn('JARVIS-OMEGA-V7.exe', document, relative)
            self.assertNotIn('dist/JARVIS-OMEGA-V7', document, relative)
            self.assertIn('dist/JARVIS-OMEGA/JARVIS-OMEGA.exe', document, relative)


if __name__ == '__main__':
    unittest.main()
