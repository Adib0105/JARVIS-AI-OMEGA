from __future__ import annotations

import time
import unittest

from jarvis.microphone import (
    WakeWordListener,
    recognition_languages,
    request_voice_interrupt,
    set_voice_interrupt_handler,
)


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


if __name__ == '__main__':
    unittest.main()
