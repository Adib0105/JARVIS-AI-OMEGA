import io
import unittest
import urllib.error
from unittest.mock import patch

from jarvis.first_run import test_provider_connection
from jarvis.updater import check_latest_release


class HttpResourceLifecycleTests(unittest.TestCase):
    @staticmethod
    def _error_opener(status, captured):
        def opener(request, timeout=0):
            body = io.BytesIO(b'{}')
            error = urllib.error.HTTPError(request.full_url, status, 'failure', {}, body)
            captured.append((error, body))
            raise error

        return opener

    def test_first_run_closes_http_error_response(self):
        captured = []
        ok, message = test_provider_connection(
            'openrouter',
            'sk-or-v1-resource-lifecycle-test',
            opener=self._error_opener(401, captured),
        )

        self.assertFalse(ok)
        self.assertIn('rejected', message)
        self.assertTrue(captured[0][0].closed)
        self.assertTrue(captured[0][1].closed)

    def test_updater_closes_http_error_response(self):
        captured = []
        with patch('jarvis.updater.urllib.request.urlopen', self._error_opener(404, captured)):
            result = check_latest_release('8.0.0-rc1')

        self.assertFalse(result['available'])
        self.assertTrue(captured[0][0].closed)
        self.assertTrue(captured[0][1].closed)


if __name__ == '__main__':
    unittest.main()
