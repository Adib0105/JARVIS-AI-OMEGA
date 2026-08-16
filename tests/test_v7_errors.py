import unittest

from jarvis.errors import ErrorCategory, classify_exception


class HTTPError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class V7ErrorClassificationTests(unittest.TestCase):
    def test_vision_400_is_not_generic_invalid_input(self):
        failure = classify_exception(HTTPError('image modality unsupported by vision model', 400))
        self.assertEqual(failure.category, ErrorCategory.VISION_ERROR)
        self.assertTrue(failure.retryable)

    def test_model_404_is_model_error(self):
        failure = classify_exception(HTTPError('model not found', 404))
        self.assertEqual(failure.category, ErrorCategory.MODEL_ERROR)
        self.assertTrue(failure.retryable)

    def test_file_not_found_remains_resource_not_found(self):
        failure = classify_exception(FileNotFoundError('notes.txt'))
        self.assertEqual(failure.category, ErrorCategory.RESOURCE_NOT_FOUND)
        self.assertFalse(failure.retryable)


if __name__ == '__main__':
    unittest.main()
