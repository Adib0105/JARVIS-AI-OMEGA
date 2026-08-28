from __future__ import annotations

import time
import unittest
from array import array

from jarvis.config import settings
from jarvis.microphone import (
    WakeWordListener,
    _pcm_rms,
    _record_until_silence,
    recognition_languages,
    request_voice_interrupt,
    set_voice_interrupt_handler,
)


class _FakeRawStream:
    def __init__(self, levels: list[int], frames: int = 3200):
        self.levels = list(levels)
        self.frames = frames
        self.reads = 0

    def read(self, frames: int):
        level = self.levels[min(self.reads, len(self.levels) - 1)] if self.levels else 0
        self.reads += 1
        samples = array('h', [level] * frames)
        return samples.tobytes(), False


class VoiceInteractionTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_voice_interrupt_handler(None)

    def test_auto_recognition_prefers_indian_english_then_hindi(self):
        self.assertEqual(recognition_languages('auto'), ('en-IN', 'hi-IN'))
        self.assertEqual(recognition_languages('hi-IN'), ('hi-IN',))

    def test_barge_in_hook_interrupts_active_voice_controller(self):
        calls = []
        set_voice_interrupt_handler(lambda: calls.append('stop'))
        self.assertTrue(request_voice_interrupt())
        self.assertEqual(calls, ['stop'])

    def test_missing_barge_in_handler_is_truthfully_reported(self):
        set_voice_interrupt_handler(None)
        self.assertFalse(request_voice_interrupt())

    def test_default_listener_uses_runtime_timing_configuration(self):
        listener = WakeWordListener(on_command=lambda _text: None)
        self.assertEqual(listener.chunk_seconds, max(2.0, min(settings.wake_chunk_seconds, 8.0)))
        self.assertEqual(
            listener.continuous_seconds,
            max(0.0, min(settings.voice_continuous_seconds, 60.0)),
        )

    def test_wake_phrase_extracts_inline_command(self):
        listener = WakeWordListener(on_command=lambda _text: None, wake_word='hey jarvis')
        woke, command = listener._command_from_heard('Hey Jarvis, open Chrome')
        self.assertTrue(woke)
        self.assertEqual(command, 'open Chrome')

    def test_continuous_window_accepts_follow_up_without_repeating_wake_word(self):
        listener = WakeWordListener(
            on_command=lambda _text: None,
            wake_word='hey jarvis',
            continuous_seconds=18.0,
        )
        listener._conversation_until = time.monotonic() + 10.0
        woke, command = listener._command_from_heard('aur browser status batao')
        self.assertFalse(woke)
        self.assertEqual(command, 'aur browser status batao')

    def test_expired_continuous_window_requires_wake_word_again(self):
        listener = WakeWordListener(
            on_command=lambda _text: None,
            wake_word='hey jarvis',
            continuous_seconds=18.0,
        )
        listener._conversation_until = time.monotonic() - 1.0
        woke, command = listener._command_from_heard('open chrome')
        self.assertFalse(woke)
        self.assertEqual(command, '')

    def test_pcm_rms_distinguishes_silence_from_clear_signal(self):
        silence = array('h', [0] * 320).tobytes()
        speech = array('h', [900] * 320).tobytes()
        self.assertEqual(_pcm_rms(silence), 0.0)
        self.assertGreater(_pcm_rms(speech), 800.0)

    def test_push_to_talk_capture_stops_after_trailing_silence(self):
        # Two quiet chunks, three speech chunks, then enough silence to trigger
        # early stop. A six-second maximum would otherwise require ~30 reads.
        stream = _FakeRawStream([0, 0, 900, 900, 900, 0, 0, 0, 0, 0, 0])
        data, speech_seen, peak = _record_until_silence(stream, 6.0, 16000)
        self.assertTrue(speech_seen)
        self.assertGreater(peak, 800.0)
        self.assertTrue(data)
        self.assertLess(stream.reads, 30)

    def test_silence_only_capture_never_claims_speech(self):
        stream = _FakeRawStream([0] * 10)
        _data, speech_seen, peak = _record_until_silence(stream, 2.0, 16000)
        self.assertFalse(speech_seen)
        self.assertEqual(peak, 0.0)


if __name__ == '__main__':
    unittest.main()
