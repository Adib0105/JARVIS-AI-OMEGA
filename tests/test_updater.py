import json
import unittest
from unittest.mock import MagicMock, patch

from jarvis.updater import check_latest_release


class _Response:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._body = json.dumps(payload).encode('utf-8')

    def read(self, _limit: int) -> bytes:
        return self._body


class UpdaterTests(unittest.TestCase):
    @patch('jarvis.updater.http.client.HTTPSConnection')
    def test_release_check_uses_fixed_https_host_and_trusted_page(self, connection_type):
        connection = MagicMock()
        connection.getresponse.return_value = _Response(200, {
            'tag_name': 'v7.5.1',
            'name': 'V7.5.1',
            'html_url': 'https://github.com/Adib0105/JARVIS-AI-OMEGA/releases/tag/v7.5.1',
        })
        connection_type.return_value = connection

        result = check_latest_release('7.5.0')

        connection_type.assert_called_once_with('api.github.com', timeout=8.0)
        self.assertTrue(result['available'])
        self.assertEqual(result['url'], 'https://github.com/Adib0105/JARVIS-AI-OMEGA/releases/tag/v7.5.1')
        connection.close.assert_called_once()

    @patch('jarvis.updater.http.client.HTTPSConnection')
    def test_untrusted_release_page_is_not_returned(self, connection_type):
        connection = MagicMock()
        connection.getresponse.return_value = _Response(200, {
            'tag_name': 'v7.5.1',
            'html_url': 'https://example.com/fake-release',
        })
        connection_type.return_value = connection

        result = check_latest_release('7.5.0')

        self.assertEqual(result['url'], '')

        connection.getresponse.return_value = _Response(200, {
            'tag_name': 'v7.5.1',
            'html_url': 'https://github.com:444/Adib0105/JARVIS-AI-OMEGA/releases/tag/v7.5.1',
        })
        self.assertEqual(check_latest_release('7.5.0')['url'], '')

    @patch('jarvis.updater.http.client.HTTPSConnection')
    def test_no_published_release_is_not_reported_as_failure(self, connection_type):
        connection = MagicMock()
        connection.getresponse.return_value = _Response(404, {})
        connection_type.return_value = connection

        result = check_latest_release('7.5.0')

        self.assertFalse(result['published'])


if __name__ == '__main__':
    unittest.main()
