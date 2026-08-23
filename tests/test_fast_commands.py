import unittest

from jarvis.fast_commands import parse_fast_command


class FastCommandTests(unittest.TestCase):
    def test_hinglish_app_open(self):
        self.assertEqual(parse_fast_command('Chrome kholo'), ('open_app', {'app': 'chrome'}))

    def test_english_app_open(self):
        self.assertEqual(parse_fast_command('open VS Code'), ('open_app', {'app': 'vscode'}))

    def test_polite_command(self):
        self.assertEqual(parse_fast_command('Jarvis please calculator open'), ('open_app', {'app': 'calculator'}))

    def test_unknown_app_falls_through_to_ai(self):
        self.assertIsNone(parse_fast_command('Photoshop kholo'))

    def test_normal_chat_is_not_hijacked(self):
        self.assertIsNone(parse_fast_command('Chrome aur Edge me kya difference hai?'))


if __name__ == '__main__':
    unittest.main()
