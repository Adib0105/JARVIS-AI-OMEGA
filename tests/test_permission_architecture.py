from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from jarvis.permissions import PermissionGate
from jarvis.security.policy import ApprovalDecision, CapabilityPermissionGate


class PermissionArchitectureTests(unittest.TestCase):
    def test_legacy_gate_is_adapter_not_independent_policy_engine(self):
        gate = PermissionGate()
        self.assertIsInstance(gate._canonical, CapabilityPermissionGate)
        self.assertFalse(hasattr(PermissionGate, 'SAFE'))
        self.assertFalse(hasattr(PermissionGate, 'APPROVAL'))

    def test_low_risk_allowed_by_canonical_policy(self):
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'false'}, clear=False):
            outcome = PermissionGate().check('get_current_time', {})
        self.assertTrue(outcome.allowed)

    def test_unknown_capability_is_denied(self):
        outcome = PermissionGate().check('totally_unknown_tool', {})
        self.assertFalse(outcome.allowed)
        self.assertEqual(outcome.decision, ApprovalDecision.DENY)

    def test_high_risk_action_requires_confirmation(self):
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'false'}, clear=False):
            outcome = PermissionGate().check('type_text', {'text': 'hello'})
        self.assertFalse(outcome.allowed)
        self.assertIn('requires user approval', outcome.reason)

    def test_confirmation_denied_blocks_execution(self):
        with patch.dict(os.environ, {'TRUSTED_LOCAL_MODE': 'false'}, clear=False):
            outcome = PermissionGate(lambda _name, _args: False).check('type_text', {'text': 'hello'})
        self.assertFalse(outcome.allowed)
        self.assertEqual(outcome.decision, ApprovalDecision.DENY)

    def test_legacy_api_respects_canonical_explicit_deny(self):
        with patch.dict(
            os.environ,
            {'TRUSTED_LOCAL_MODE': 'false', 'PERMISSION_SYSTEM_READ': 'deny'},
            clear=False,
        ):
            outcome = PermissionGate(lambda _name, _args: True).check('get_current_time', {})
        self.assertFalse(outcome.allowed)
        self.assertIn('SYSTEM_READ', outcome.reason)

    def test_privilege_escalation_cannot_turn_unknown_tool_into_allowed(self):
        with patch.dict(
            os.environ,
            {'TRUSTED_LOCAL_MODE': 'true', 'REQUIRE_LOCAL_APPROVAL': 'false'},
            clear=False,
        ):
            outcome = PermissionGate(lambda _name, _args: True).check(
                'shell_execute_unprofiled', {'command': 'whoami'}
            )
        self.assertFalse(outcome.allowed)


if __name__ == '__main__':
    unittest.main()
