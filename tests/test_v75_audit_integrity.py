import tempfile
import unittest
from pathlib import Path

from jarvis.security.audit import AuditStore
from jarvis.security.center import SecurityCenter


class V75AuditIntegrityTests(unittest.TestCase):
    def _record(self, store: AuditStore) -> int:
        return store.record(
            mission_id='MSN-1',
            session_id='S-1',
            request_summary='open chrome',
            tool_name='open_app',
            risk_level='MEDIUM',
            capabilities=['APP_CONTROL'],
            args={'app': 'chrome'},
            approval_status='AUTO_ALLOWED',
            execution_status='SUCCESS',
            provider='test',
            model='test-model',
        )

    def test_new_audit_record_and_verification_form_valid_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            audit_id = self._record(store)
            first = store.verify_integrity()
            self.assertTrue(first['ok'])
            self.assertEqual(first['status'], 'OK')
            self.assertEqual(first['chained_audit_rows'], 1)
            store.update_verification(audit_id, 'VERIFIED')
            second = store.verify_integrity()
            self.assertTrue(second['ok'])
            self.assertEqual(second['integrity_events'], 2)
            self.assertTrue(second['head_hash'])

    def test_mutating_chained_audit_payload_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            audit_id = self._record(store)
            with store._connect() as conn:
                conn.execute(
                    'UPDATE v7_audit_log SET tool_name=? WHERE id=?',
                    ('tampered_tool', audit_id),
                )
                conn.commit()
            result = store.verify_integrity()
            self.assertFalse(result['ok'])
            self.assertEqual(result['status'], 'BROKEN')
            self.assertEqual(result['first_bad_audit_id'], audit_id)
            self.assertIn('modified', result['reason'].lower())

    def test_mutating_current_verification_result_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            audit_id = self._record(store)
            store.update_verification(audit_id, 'VERIFIED')
            with store._connect() as conn:
                conn.execute(
                    'UPDATE v7_audit_log SET verification_result=? WHERE id=?',
                    ('FAILED', audit_id),
                )
                conn.commit()
            result = store.verify_integrity()
            self.assertFalse(result['ok'])
            self.assertEqual(result['first_bad_audit_id'], audit_id)

    def test_legacy_unchained_rows_are_reported_not_falsely_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            with store._connect() as conn:
                conn.execute(
                    '''INSERT INTO v7_audit_log(
                        timestamp, mission_id, session_id, request_summary, tool_name,
                        risk_level, capabilities_json, arguments_hash, approval_status,
                        execution_status, error_type, latency_ms, provider, model,
                        verification_result
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        '2026-01-01T00:00:00+00:00', None, None, 'legacy', 'get_system_info',
                        'LOW', '[]', '0' * 64, 'AUTO_ALLOWED', 'SUCCESS', None, 1.0,
                        'legacy', 'legacy', None,
                    ),
                )
                conn.commit()
            result = store.verify_integrity()
            self.assertTrue(result['ok'])
            self.assertEqual(result['status'], 'LEGACY_UNCHAINED')
            self.assertEqual(result['legacy_unchained_rows'], 1)

    def test_security_center_surfaces_integrity_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuditStore(Path(tmp) / 'audit.db')
            self._record(store)
            snapshot = SecurityCenter(store).snapshot()
            self.assertIn('audit_integrity', snapshot)
            self.assertTrue(snapshot['audit_integrity']['ok'])


if __name__ == '__main__':
    unittest.main()
