import unittest

from jarvis.logging_utils import redact_text, redact_value


class V7LoggingTests(unittest.TestCase):
    def test_openai_style_key_is_redacted(self):
        value = redact_text('OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456')
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz123456', value)
        self.assertIn('[REDACTED]', value)

    def test_prefixed_api_key_assignment_is_redacted_without_known_key_prefix(self):
        value = redact_text('OPENROUTER_API_KEY=nonstandard-real-key-value')
        self.assertNotIn('nonstandard-real-key-value', value)
        self.assertIn('[REDACTED]', value)

    def test_openrouter_key_is_redacted(self):
        secret = 'sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890'
        value = redact_text(f'Authorization: Bearer {secret}')
        self.assertNotIn(secret, value)
        self.assertIn('[REDACTED]', value)

    def test_structured_secret_fields_are_redacted_recursively(self):
        value = redact_value({
            'provider': 'openrouter',
            'api_key': 'do-not-log-me',
            'nested': {'refresh_token': 'also-secret', 'safe': 'hello'},
        })
        self.assertEqual(value['api_key'], '[REDACTED]')
        self.assertEqual(value['nested']['refresh_token'], '[REDACTED]')
        self.assertEqual(value['nested']['safe'], 'hello')

    def test_json_quoted_basic_jwt_and_url_credentials_are_redacted(self):
        jwt = 'eyJabcdefghijk.abcdefghijk.abcdefghijk'
        value = redact_text(
            '{"api_key": "super secret value"} '
            'Authorization: Basic dXNlcjpwYXNzd29yZA== '
            f'token={jwt} https://user:password@example.com/path'
        )
        for secret in ('super secret value', 'dXNlcjpwYXNzd29yZA==', jwt, 'user:password'):
            self.assertNotIn(secret, value)


if __name__ == '__main__':
    unittest.main()
