import unittest

from jarvis.common.results import OperationResult, OperationStatus


class OperationResultTests(unittest.TestCase):
    def test_verified_requires_success(self):
        result = OperationResult.verified_result(
            'file hash matched', capability='File Write', evidence=['sha256:abc'], duration_ms=12.5
        )
        self.assertTrue(result.success)
        self.assertTrue(result.verified)
        self.assertEqual(result.status, OperationStatus.VERIFIED)
        self.assertEqual(result.as_dict()['status'], 'VERIFIED')
        self.assertEqual(result.as_dict()['ok'], True)

    def test_unverified_success_is_not_promoted_to_verified(self):
        result = OperationResult.from_legacy({'ok': True, 'message': 'browser requested open'}, capability='Browser')
        self.assertTrue(result.success)
        self.assertFalse(result.verified)
        self.assertEqual(result.status, OperationStatus.UNVERIFIED)

    def test_partial_verification_remains_partial(self):
        result = OperationResult.from_legacy({
            'ok': True,
            'verification': {'status': 'PARTIAL', 'evidence': 'browser process exists'},
        }, capability='Browser')
        self.assertEqual(result.status, OperationStatus.PARTIAL)
        self.assertFalse(result.verified)
        self.assertIn('browser process exists', result.evidence)

    def test_failed_result_cannot_claim_success(self):
        with self.assertRaises(ValueError):
            OperationResult(True, OperationStatus.FAILED, 'impossible')
        result = OperationResult.failed('permission denied', capability='Tool')
        self.assertFalse(result.success)
        self.assertEqual(result.status, OperationStatus.FAILED)
        self.assertTrue(result.errors)

    def test_plain_legacy_string_is_unverified_not_verified(self):
        result = OperationResult.from_legacy('done', capability='Legacy Tool')
        self.assertTrue(result.success)
        self.assertEqual(result.status, OperationStatus.UNVERIFIED)
        self.assertFalse(result.verified)

    def test_metadata_flattening_never_overwrites_canonical_status(self):
        result = OperationResult.unverified(
            'attempted', metadata={'status': 'VERIFIED', 'action': 'open'}, capability='Browser'
        )
        payload = result.as_dict(flatten_metadata=True)
        self.assertEqual(payload['status'], 'UNVERIFIED')
        self.assertEqual(payload['action'], 'open')


if __name__ == '__main__':
    unittest.main()
