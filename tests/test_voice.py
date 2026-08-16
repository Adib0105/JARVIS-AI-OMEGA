import unittest

from jarvis.voice import clean_for_speech, detect_speech_mode, edge_rate_for_speed


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

    def test_edge_speed_keeps_configured_base_at_normal_speed(self):
        self.assertEqual(edge_rate_for_speed('-2%', 1.0), '-2%')

    def test_edge_speed_converts_multiplier_to_rate(self):
        self.assertEqual(edge_rate_for_speed('-2%', 1.2), '+18%')
        self.assertEqual(edge_rate_for_speed('-2%', 0.8), '-22%')

    def test_edge_speed_is_clamped_to_provider_safe_range(self):
        self.assertEqual(edge_rate_for_speed('+0%', 0.1), '-50%')
        self.assertEqual(edge_rate_for_speed('+0%', 3.0), '+100%')


if __name__ == '__main__':
    unittest.main()
