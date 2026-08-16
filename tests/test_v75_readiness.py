import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.readiness import ReadinessCheck, ReleaseReadinessCertifier


class V75ReadinessTests(unittest.TestCase):
    def _certifier(self, root: Path, *, mic=True, google=False, api_key='configured'):
        settings = SimpleNamespace(
            db_path=root / 'state.db',
            require_approval_for_production=True,
            production_self_modification=False,
            enable_mic_input=mic,
            enable_google_workspace=google,
            api_key=api_key,
        )
        return ReleaseReadinessCertifier(
            root=root,
            db_path=settings.db_path,
            settings_obj=settings,
        )

    def test_software_pass_does_not_fake_live_release_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            certifier = self._certifier(Path(tmp))
            with patch.object(
                certifier,
                '_automated_checks',
                return_value=[ReadinessCheck('software', 'PASS', 'ok')],
            ):
                report = certifier.certify().as_dict()
            self.assertTrue(report['software_ready'])
            self.assertFalse(report['final_release_ready'])
            pending = {
                row['name'] for row in report['checks']
                if row['status'] == 'NOT_VERIFIED' and row['required']
            }
            self.assertIn('desktop_gui', pending)
            self.assertIn('microphone_live', pending)
            self.assertIn('provider_live', pending)

    def test_explicit_live_evidence_can_complete_release_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            certifier = self._certifier(Path(tmp), mic=False, google=False)
            evidence = {
                'desktop_gui': {'ok': True, 'detail': 'desktop smoke passed'},
                'computer_use': True,
                'provider_live': True,
                'windows_package_launch': True,
                'inno_installer_install_uninstall': True,
            }
            with patch.object(
                certifier,
                '_automated_checks',
                return_value=[ReadinessCheck('software', 'PASS', 'ok')],
            ):
                report = certifier.certify(evidence).as_dict()
            self.assertTrue(report['software_ready'])
            self.assertTrue(report['final_release_ready'])
            self.assertEqual(report['not_verified'], 0)

    def test_failed_live_evidence_blocks_final_release_not_software_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            certifier = self._certifier(Path(tmp), mic=False)
            evidence = {
                'desktop_gui': False,
                'computer_use': True,
                'provider_live': True,
                'windows_package_launch': True,
                'inno_installer_install_uninstall': True,
            }
            with patch.object(
                certifier,
                '_automated_checks',
                return_value=[ReadinessCheck('software', 'PASS', 'ok')],
            ):
                report = certifier.certify(evidence).as_dict()
            self.assertTrue(report['software_ready'])
            self.assertFalse(report['final_release_ready'])

    def test_automated_failure_blocks_software_and_final_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            certifier = self._certifier(Path(tmp), mic=False, api_key='')
            with patch.object(
                certifier,
                '_automated_checks',
                return_value=[ReadinessCheck('database', 'FAIL', 'corrupt')],
            ):
                report = certifier.certify({}).as_dict()
            self.assertFalse(report['software_ready'])
            self.assertFalse(report['final_release_ready'])


if __name__ == '__main__':
    unittest.main()
