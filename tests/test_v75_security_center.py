import tempfile
import unittest
from pathlib import Path

from jarvis.security.audit import AuditStore
from jarvis.security.center import SecurityCenter


class V75SecurityCenterTests(unittest.TestCase):
    def test_snapshot_contains_policies_dangerous_tools_and_blocked_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditStore(Path(tmp) / 'jarvis.db')
            audit.record(
                mission_id='M1', session_id='S1', request_summary='blocked action',
                tool_name='type_text', risk_level='HIGH', capabilities=['KEYBOARD_CONTROL'],
                args={'text': 'secret'}, approval_status='DENY', execution_status='DENIED',
            )
            center = SecurityCenter(audit)
            snapshot = center.snapshot()
            self.assertTrue(snapshot['policies'])
            self.assertTrue(snapshot['dangerous_tools'])
            self.assertEqual(snapshot['recent_blocked'][0]['tool_name'], 'type_text')
            self.assertTrue(snapshot['approval_history'])
            self.assertIsInstance(snapshot['trusted_local_mode'], bool)


if __name__ == '__main__':
    unittest.main()
