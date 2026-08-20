import unittest

from jarvis.microphone import _rms_int16
from jarvis.voice_personality import speechify


class PremiumVoiceFormattingTests(unittest.TestCase):
    def test_speechify_removes_markdown_url_emoji_and_visual_noise(self):
        spoken = speechify('**CPU usage:** 72%. ✅ See https://example.com/test')
        self.assertNotIn('**', spoken)
        self.assertNotIn('https://', spoken)
        self.assertNotIn('✅', spoken)
        self.assertIn('72 percent', spoken)
        self.assertIn('link shown on screen', spoken)

    def test_code_block_is_not_read_verbatim(self):
        spoken = speechify("Use this:\n```python\nprint('secret')\n```\nDone")
        self.assertNotIn('secret', spoken)
        self.assertIn('code is shown on screen', spoken.lower())

    def test_long_identifier_is_not_spoken(self):
        spoken = speechify('Request abcdef1234567890abcdef1234567890 failed')
        self.assertNotIn('abcdef1234567890', spoken)
        self.assertIn('identifier shown on screen', spoken)

    def test_empty_text_stays_empty(self):
        self.assertEqual(speechify('   '), '')


class VadMathTests(unittest.TestCase):
    def test_silence_has_zero_rms(self):
        self.assertEqual(_rms_int16(b'\x00\x00' * 100), 0.0)

    def test_nonzero_audio_has_positive_rms(self):
        # little-endian signed 16-bit sample 1000 repeated
        self.assertGreater(_rms_int16(b'\xe8\x03' * 100), 900.0)


if __name__ == '__main__':
    unittest.main()
