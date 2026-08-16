import unittest

from jarvis.voice import clean_for_speech, detect_speech_mode


class VoiceCleaningTests(unittest.TestCase):
    def test_markdown_and_link_cleanup(self):
        text = "**Hello** [Adib](https://example.com)"
        self.assertEqual(clean_for_speech(text), "Hello Adib")

    def test_code_block_is_not_read_verbatim(self):
        text = "Run this: ```python\nprint('secret')\n``` done"
        spoken = clean_for_speech(text)
        self.assertIn("Code block speech me skip kiya gaya.", spoken)
        self.assertNotIn("print", spoken)

    def test_emoji_removed_from_speech(self):
        self.assertEqual(clean_for_speech('Main theek hoon 😊 bhai'), 'Main theek hoon bhai')

    def test_devanagari_detects_hindi(self):
        self.assertEqual(detect_speech_mode("नमस्ते आदिब, आप कैसे हैं?"), "hindi")

    def test_roman_hindi_detects_hinglish(self):
        self.assertEqual(detect_speech_mode("bhai mujhe batao ye kaise karna hai"), "hinglish")

    def test_plain_english_detects_english(self):
        self.assertEqual(detect_speech_mode("Explain this Python function clearly"), "english")


if __name__ == '__main__':
    unittest.main()
