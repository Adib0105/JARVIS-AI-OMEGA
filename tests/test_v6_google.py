import tempfile
import unittest
from pathlib import Path

from jarvis.google_workspace import GoogleWorkspace, SCOPES


class V6GoogleWorkspaceTests(unittest.TestCase):
    def test_configuration_is_local_and_non_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = GoogleWorkspace(root / 'credentials.json', root / 'token.json')
            status = workspace.configured()
            self.assertFalse(status['credentials_exists'])
            self.assertFalse(status['token_exists'])
            self.assertIn('gmail.readonly', ' '.join(SCOPES))
            self.assertIn('calendar.events', ' '.join(SCOPES))

    def test_send_rejects_invalid_recipient_before_oauth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = GoogleWorkspace(root / 'credentials.json', root / 'token.json')
            with self.assertRaises(ValueError):
                workspace.gmail_send('not-an-email', 'subject', 'body')


if __name__ == '__main__':
    unittest.main()
