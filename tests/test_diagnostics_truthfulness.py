from __future__ import annotations

import unittest

from jarvis.diagnostics import DiagnosticResult, DiagnosticState


class DiagnosticTruthfulnessTests(unittest.TestCase):
    def test_required_verification_states_exist(self):
        expected = {
            'INSTALLED', 'CONFIGURED', 'LOCAL_FUNCTIONAL', 'INTEGRATION_TESTED',
            'DEVICE_VERIFIED', 'E2E_VERIFIED', 'DEGRADED', 'FAILED', 'NOT_TESTED',
        }
        self.assertEqual({state.value for state in DiagnosticState}, expected)

    def test_installed_does_not_imply_functional_or_verified(self):
        installed = DiagnosticResult('microphone package', DiagnosticState.INSTALLED)
        device = DiagnosticResult('microphone device', DiagnosticState.NOT_TESTED)
        self.assertEqual(installed.state, DiagnosticState.INSTALLED)
        self.assertNotEqual(installed.state, DiagnosticState.LOCAL_FUNCTIONAL)
        self.assertNotEqual(installed.state, DiagnosticState.DEVICE_VERIFIED)
        self.assertEqual(device.state, DiagnosticState.NOT_TESTED)

    def test_not_tested_is_not_failed(self):
        result = DiagnosticResult('live provider', DiagnosticState.NOT_TESTED, required=True)
        self.assertFalse(result.failed)

    def test_only_failed_state_is_a_failure(self):
        for state in DiagnosticState:
            result = DiagnosticResult('check', state)
            self.assertEqual(result.failed, state == DiagnosticState.FAILED)

    def test_rendered_line_preserves_exact_state(self):
        result = DiagnosticResult('audible TTS', DiagnosticState.NOT_TESTED, 'speaker not exercised')
        self.assertEqual(result.line(), '[NOT_TESTED] audible TTS - speaker not exercised')


if __name__ == '__main__':
    unittest.main()
