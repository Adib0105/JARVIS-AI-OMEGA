import unittest

from jarvis.errors import ErrorCategory, ErrorCode, classify_exception
from jarvis.providers.deadline import RequestCancelledError


class HTTPError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class V7ErrorClassificationTests(unittest.TestCase):
    def test_vision_400_is_not_generic_invalid_input(self):
        failure = classify_exception(HTTPError('image modality unsupported by vision model', 400))
        self.assertEqual(failure.category, ErrorCategory.VISION_ERROR)
        self.assertEqual(failure.code, ErrorCode.PROVIDER_ERROR)
        self.assertTrue(failure.retryable)

    def test_model_404_is_model_error(self):
        failure = classify_exception(HTTPError('model not found', 404))
        self.assertEqual(failure.category, ErrorCategory.MODEL_ERROR)
        self.assertEqual(failure.canonical_code, ErrorCode.PROVIDER_ERROR)
        self.assertTrue(failure.retryable)

    def test_file_not_found_remains_resource_not_found(self):
        failure = classify_exception(FileNotFoundError('notes.txt'))
        self.assertEqual(failure.category, ErrorCategory.RESOURCE_NOT_FOUND)
        self.assertEqual(failure.code, ErrorCode.RESOURCE_NOT_FOUND_ERROR)
        self.assertFalse(failure.retryable)

    def test_authentication_and_authorization_are_distinct_in_v8_taxonomy(self):
        auth = classify_exception(HTTPError('invalid api key', 401), provider='openrouter', operation='chat')
        denied = classify_exception(PermissionError('permission denied'), operation='tool')
        self.assertEqual(auth.category, ErrorCategory.AUTH_ERROR)  # legacy compatibility
        self.assertEqual(auth.code, ErrorCode.AUTHENTICATION_ERROR)
        self.assertEqual(denied.category, ErrorCategory.PERMISSION_ERROR)
        self.assertEqual(denied.code, ErrorCode.AUTHORIZATION_ERROR)

    def test_user_cancellation_is_not_reported_as_timeout_or_generic_permission(self):
        failure = classify_exception(RequestCancelledError('AI request was cancelled.'), operation='chat')
        self.assertEqual(failure.code, ErrorCode.USER_CANCELLED)
        self.assertFalse(failure.retryable)

    def test_domain_operation_maps_unknown_exception_to_actionable_code(self):
        browser = classify_exception(RuntimeError('renderer crashed unexpectedly'), operation='browser.read')
        sandbox = classify_exception(RuntimeError('worktree disappeared'), operation='self_development.sandbox')
        release = classify_exception(RuntimeError('fast-forward precondition failed'), operation='release.deploy')
        storage = classify_exception(RuntimeError('database locked unexpectedly'), operation='storage.restore')
        self.assertEqual(browser.code, ErrorCode.BROWSER_ERROR)
        self.assertEqual(sandbox.code, ErrorCode.SANDBOX_ERROR)
        self.assertEqual(release.code, ErrorCode.RELEASE_ERROR)
        self.assertEqual(storage.code, ErrorCode.STORAGE_ERROR)


if __name__ == '__main__':
    unittest.main()
