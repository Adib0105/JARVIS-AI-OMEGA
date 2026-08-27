from __future__ import annotations

import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import desktop_app
from jarvis import voice as voice_module
from jarvis.tts_worker import synthesize_and_play
from jarvis.voice import VoiceOutput


class PackagedTTSRuntimeTests(unittest.TestCase):
    def _voice_for_worker(self, playback_result: str):
        voice = VoiceOutput.__new__(VoiceOutput)
        voice.enabled = True
        voice.muted = False
        voice.on_state_change = lambda state: self.states.append(state)
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
        voice._process = None
        voice._offline_engine = None
        voice._play_text = lambda _text: playback_result
        return voice

    def test_desktop_routes_frozen_edge_playback_before_gui_bootstrap(self):
        argv = [
            r'C:\Program Files\JARVIS AI OMEGA\JARVIS-OMEGA-V7.exe',
            '-m', 'edge_playback', '--voice', 'en-IN-PrabhatNeural', '--file', 'speech.txt',
        ]
        with patch.object(desktop_app.sys, 'argv', argv):
            with patch('jarvis.tts_worker.run_edge_playback_worker', return_value=0) as worker:
                result = desktop_app.main()
        self.assertEqual(result, 0)
        worker.assert_called_once_with(argv[3:])

    def test_desktop_routes_frozen_offline_playback_before_gui_bootstrap(self):
        argv = [
            r'C:\Program Files\JARVIS AI OMEGA\JARVIS-OMEGA-V7.exe',
            '--offline-tts-playback', '--file', 'speech.txt',
        ]
        with patch.object(desktop_app.sys, 'argv', argv):
            with patch('jarvis.offline_tts_worker.run_offline_playback_worker', return_value=0) as worker:
                result = desktop_app.main()
        self.assertEqual(result, 0)
        worker.assert_called_once_with(argv[2:])

    def test_frozen_parent_command_targets_worker_route_not_source_script(self):
        voice = VoiceOutput.__new__(VoiceOutput)
        voice._lock = threading.RLock()
        voice._speed = 1.0
        voice._interrupt_reason = None
        voice._process = None

        captured = {}

        class FakeProcess:
            pid = 12345
            def wait(self, timeout=None):
                captured['wait_timeout'] = timeout
                return 0
            def poll(self):
                return 0

        def fake_popen(command, **kwargs):
            captured['command'] = list(command)
            captured['kwargs'] = dict(kwargs)
            return FakeProcess()

        frozen_exe = r'C:\Program Files\JARVIS AI OMEGA\JARVIS-OMEGA-V7.exe'
        with patch.object(voice_module.sys, 'executable', frozen_exe), patch.object(
            voice_module.subprocess, 'Popen', side_effect=fake_popen
        ):
            result = voice._speak_edge('hello')

        self.assertEqual(result, 'completed')
        self.assertEqual(captured['command'][0], frozen_exe)
        self.assertEqual(captured['command'][1:3], ['-m', 'edge_playback'])
        self.assertNotIn('desktop_app.py', captured['command'])
        self.assertGreater(captured['wait_timeout'], 0)
        self.assertLessEqual(captured['wait_timeout'], 180)

    def test_worker_synthesizes_with_edge_tts_and_invokes_native_playback(self):
        created = {}

        class FakeCommunicate:
            def __init__(self, text, voice, **kwargs):
                created['text'] = text
                created['voice'] = voice
                created['kwargs'] = dict(kwargs)
            def save_sync(self, path):
                Path(path).write_bytes(b'fake-mp3-data')
                created['media'] = path

        with patch('jarvis.tts_worker.edge_tts.Communicate', FakeCommunicate), patch(
            'jarvis.tts_worker.play_mp3_windows'
        ) as playback:
            synthesize_and_play(
                'JARVIS ONLINE',
                voice='en-IN-PrabhatNeural',
                rate='-2%',
                volume='+5%',
                pitch='-20Hz',
            )

        self.assertEqual(created['text'], 'JARVIS ONLINE')
        self.assertEqual(created['voice'], 'en-IN-PrabhatNeural')
        self.assertEqual(created['kwargs']['rate'], '-2%')
        playback.assert_called_once()
        self.assertFalse(Path(created['media']).exists())

    def test_tts_success_state_returns_speaking_to_idle(self):
        self.states = []
        voice = self._voice_for_worker('completed')
        voice._queue.put('hello')
        voice._queue.put(voice_module._SENTINEL)
        voice._worker()
        self.assertIn('speaking', self.states)
        self.assertEqual(voice.state, 'idle')
        self.assertNotEqual(voice.state, 'speaking')

    def test_tts_failure_surfaces_error_state_then_returns_idle(self):
        self.states = []
        voice = self._voice_for_worker('failed')
        voice._queue.put('hello')
        voice._queue.put(voice_module._SENTINEL)
        voice._worker()
        self.assertIn('speaking', self.states)
        self.assertIn('error', self.states)
        self.assertEqual(voice.state, 'idle')
        self.assertLess(self.states.index('speaking'), self.states.index('error'))
        self.assertLess(self.states.index('error'), len(self.states) - 1)

    def test_repeated_tts_requests_each_return_to_idle(self):
        self.states = []
        voice = self._voice_for_worker('completed')
        voice._queue.put('first')
        voice._queue.put('second')
        voice._queue.put(voice_module._SENTINEL)
        voice._worker()
        self.assertEqual(self.states.count('speaking'), 2)
        self.assertEqual(self.states[-1], 'idle')

    def test_primary_edge_failure_uses_configured_fallback(self):
        voice = VoiceOutput.__new__(VoiceOutput)
        calls = []
        voice._speak_edge_voice = lambda _text, selected, _timeout: calls.append(selected) or (
            'failed' if len(calls) == 1 else 'completed'
        )
        result = voice._speak_edge('hello')
        self.assertEqual(result, 'completed')
        self.assertEqual(calls[:2], [voice_module.settings.voice_english, voice_module.settings.voice_fallback])

    def test_frozen_offline_fallback_uses_dedicated_worker_route(self):
        voice = VoiceOutput.__new__(VoiceOutput)
        voice._lock = threading.RLock()
        voice._speed = 1.0
        voice._interrupt_reason = None
        voice._process = None
        captured = {}

        class FakeProcess:
            pid = 123
            def wait(self, timeout=None):
                captured['timeout'] = timeout
                return 0
            def poll(self):
                return 0

        def fake_popen(command, **kwargs):
            captured['command'] = list(command)
            return FakeProcess()

        with patch.object(voice_module.sys, 'frozen', True, create=True), patch.object(
            voice_module.sys, 'executable', r'C:\Program Files\JARVIS AI OMEGA\JARVIS-OMEGA-V7.exe'
        ), patch.object(voice_module.subprocess, 'Popen', side_effect=fake_popen):
            result = voice._speak_offline('fallback speech')

        self.assertEqual(result, 'completed')
        self.assertEqual(captured['command'][1], '--offline-tts-playback')
        self.assertNotIn('desktop_app.py', captured['command'])
        self.assertGreater(captured['timeout'], 0)

    def test_stop_mute_unmute_do_not_disable_future_speech(self):
        voice = VoiceOutput.__new__(VoiceOutput)
        voice.enabled = True
        voice.muted = False
        voice._queue = queue.Queue()
        voice._lock = threading.RLock()
        voice._condition = threading.Condition(voice._lock)
        voice._cancel_epoch = 0
        voice._paused = False
        voice._interrupt_reason = None
        voice._process = None
        voice._offline_engine = None
        voice._state = 'idle'
        voice._shutdown = False
        voice.on_state_change = lambda _state: None
        voice.mute()
        self.assertTrue(voice.muted)
        voice.speak('ignored')
        self.assertTrue(voice._queue.empty())
        voice.unmute()
        voice.speak('accepted')
        self.assertFalse(voice._queue.empty())


if __name__ == '__main__':
    unittest.main()
