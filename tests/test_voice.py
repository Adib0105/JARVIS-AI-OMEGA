import unittest

from jarvis.voice import clean_for_speech


class VoiceCleaningTests(unittest.TestCase):
    def test_markdown_and_link_cleanup(self):
        text = "**Hello** [Adib](https://example.com)"
        self.assertEqual(clean_for_speech(text), "Hello Adib")

    def test_code_block_is_not_read_verbatim(self):
        text = "Run this: ```python\nprint('secret')\n``` done"
        spoken = clean_for_speech(text)
        self.assertIn("Code block omitted from speech.", spoken)
        self.assertNotIn("print", spoken)


if __name__ == '__main__':
    unittest.main()
