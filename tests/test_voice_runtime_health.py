from __future__ import annotations

import unittest

from jarvis.config import settings
from jarvis.tts_worker import runtime_healthcheck


class VoiceRuntimeHealthTests(unittest.TestCase):
    def test_healthcheck_exposes_configured_emotional_voice_capabilities(self):
        report = runtime_healthcheck()
        self.assertEqual(report['voice_profile'], settings.voice_profile)
        self.assertEqual(report['configured_voice'], settings.voice_english)
        self.assertEqual(report['configured_hinglish_voice'], settings.voice_hinglish)
        self.assertEqual(report['configured_hindi_voice'], settings.voice_hindi)
        self.assertEqual(report['emotion_enabled'], settings.voice_emotion_enabled)
        self.assertEqual(report['streaming_enabled'], settings.voice_streaming_enabled)
        self.assertEqual(report['barge_in_enabled'], settings.voice_barge_in)

    def test_automated_healthcheck_never_fakes_physical_audio_or_microphone_proof(self):
        report = runtime_healthcheck()
        self.assertIs(report['audible_playback_verified'], False)
        self.assertIs(report['physical_microphone_verified'], False)


if __name__ == '__main__':
    unittest.main()
