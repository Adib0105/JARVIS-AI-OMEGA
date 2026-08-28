from __future__ import annotations

import queue
import threading
import unittest

from jarvis import voice as voice_module
from jarvis.voice import VoiceOutput
from jarvis.voice_profiles import detect_emotion, speech_chunks, voice_style


class EmotionalVoiceTests(unittest.TestCase):
    def _bare_voice(self) -> VoiceOutput:
        voice = VoiceOutput.__new__(VoiceOutput)
        voice.enabled = True
        voice.muted = False
        voice.on_state_change = lambda _state: None
        voice._queue = queue.Queue()
        voice._lock = threading.RLock()
        voice._condition = threading.Condition(voice._lock)
        voice._shutdown = False
        voice._paused = False
        voice._state = 'idle'
        voice._speed = 1.0
        voice._cancel_epoch = 0
        voice._interrupt_reason = None
        voice._current_text = None
        voice._last_text = None
        voice._current_emotion = 'calm'
        voice._current_style = voice_style('calm')
        voice._process = None
        voice._offline_engine = None
        return voice

    def test_emotion_detector_distinguishes_core_modes(self):
        self.assertEqual(detect_emotion('Great, everything completed successfully!'), 'happy')
        self.assertEqual(detect_emotion('Warning: critical failure, act immediately.'), 'urgent')
        self.assertEqual(detect_emotion('Sorry, there is a problem. Please be careful.'), 'concerned')
        self.assertEqual(detect_emotion('Project status report and release review.'), 'professional')
        self.assertEqual(detect_emotion('I am here and ready to help.'), 'happy')

    def test_historical_small_chunk_setting_no_longer_splits_normal_reply(self):
        text = 'First sentence is ready. Second sentence is also ready. Third sentence is here.'
        chunks = speech_chunks(text, max_chars=80)
        self.assertEqual(chunks, [text])

    def test_short_multi_sentence_reply_is_not_split_line_by_line(self):
        text = (
            'System check completed successfully. '
            'The browser security layer is ready. '
            'Computer control verification is also ready.'
        )
        chunks = speech_chunks(text, max_chars=260)
        self.assertEqual(chunks, [text])

    def test_multi_paragraph_sized_reply_stays_single_continuous_utterance(self):
        sentence = 'This sentence carries enough detail to exercise continuous neural speech playback safely.'
        text = ' '.join([sentence] * 35)
        self.assertLess(len(text), 5000)
        chunks = speech_chunks(text, max_chars=260)
        self.assertEqual(chunks, [text])

    def test_genuinely_huge_reply_is_still_bounded(self):
        sentence = 'This is a deliberately long sentence for bounded neural speech synthesis and interruption testing.'
        text = ' '.join([sentence] * 90)
        self.assertGreater(len(text), 6000)
        chunks = speech_chunks(text, max_chars=260)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(' '.join(chunks), text)
        self.assertTrue(all(len(chunk) <= 5000 for chunk in chunks))

    def test_speak_queues_one_continuous_item_for_normal_multi_sentence_answer(self):
        voice = self._bare_voice()
        text = (
            'System check completed successfully. '
            'The browser security layer is ready. '
            'Computer control verification is also ready.'
        )
        voice.speak(text, emotion='professional', stream=True)
        queued = []
        while not voice._queue.empty():
            queued.append(voice._queue.get_nowait())
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].text, text)
        self.assertEqual(queued[0].emotion, 'professional')

    def test_happy_profile_uses_subtle_prosody_without_robotic_pitch_jump(self):
        voice = self._bare_voice()
        voice._current_emotion = 'happy'
        voice._current_style = voice_style('happy')
        rate, volume, pitch = voice._edge_parameters('Great, done successfully!')
        self.assertEqual(rate, '+0%')
        self.assertEqual(volume, '+2%')
        self.assertEqual(pitch, '+4Hz')
        self.assertEqual(voice._current_style.pause_after_ms, 0)

    def test_stream_api_accepts_incremental_model_chunks(self):
        voice = self._bare_voice()
        voice.speak_stream(['Hello. ', 'Main ready hoon.'], request_id='req-1', emotion='calm')
        items = [voice._queue.get_nowait(), voice._queue.get_nowait()]
        self.assertEqual([item.request_id for item in items], ['req-1', 'req-1'])
        self.assertTrue(all(item.emotion == 'calm' for item in items))

    def test_primary_voice_profile_is_indian_female(self):
        self.assertEqual(voice_module.settings.voice_english, 'en-IN-NeerjaNeural')
        self.assertEqual(voice_module.settings.voice_hinglish, 'en-IN-NeerjaNeural')
        self.assertEqual(voice_module.settings.voice_hindi, 'hi-IN-SwaraNeural')
        self.assertEqual(voice_module.settings.voice_profile, 'indian-female-emotional')


if __name__ == '__main__':
    unittest.main()
