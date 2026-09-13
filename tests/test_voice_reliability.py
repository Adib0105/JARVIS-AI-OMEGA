import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.config import settings
from jarvis.voice import VoiceOutput, _SENTINEL
from jarvis.speech_worker import main as speech_main, speech_chunks, render_openai, speak_offline, speak_windows_sapi
from jarvis.voice_personality import speechify
from jarvis.microphone import record_until_silence, WakeWordListener


class VoiceReliabilityTests(unittest.TestCase):
    def voice(self):
        with patch('jarvis.voice.settings', replace(settings, enable_voice_output=False)):
            voice = VoiceOutput()
        voice.enabled = True
        self.addCleanup(voice.shutdown)
        return voice

    def test_stop_discards_dequeued_old_generation(self):
        voice = self.voice()
        old = (voice._cancel_epoch, 'old speech')
        voice.stop()
        voice._queue.put(old)  # Simulate dequeue racing with STOP.
        voice._queue.put(_SENTINEL)
        with patch.object(voice, '_play_text') as play:
            voice._worker()
        play.assert_not_called()

    def test_stop_between_state_callback_and_process_creation(self):
        voice = self.voice()
        voice.speak('hello')
        def stop_on_start(state):
            if state == 'speaking':
                voice.stop()
                voice._queue.put(_SENTINEL)
        voice.on_state_change = stop_on_start
        with patch('jarvis.voice.subprocess.Popen') as popen:
            voice._worker()
        popen.assert_not_called()

    def test_pause_resume_before_process_finishes_replays(self):
        voice = self.voice()
        voice.speak('hello')
        calls = []
        def play(text):
            calls.append(text)
            if len(calls) == 1:
                voice.pause()
                voice.resume()
                return 'interrupted'
            voice._queue.put(_SENTINEL)
            return 'completed'
        with patch.object(voice, '_play_text', side_effect=play):
            voice._worker()
        self.assertEqual(calls, ['hello', 'hello'])

    def test_failure_stays_visible(self):
        voice = self.voice()
        def play(_):
            voice._queue.put(_SENTINEL)
            return 'failed'
        states = []
        voice.on_state_change = states.append
        voice.speak('hello')
        with patch.object(voice, '_play_text', side_effect=play):
            voice._worker()
        # The last idle is worker shutdown, not an immediate reset after failure.
        self.assertEqual(states, ['speaking', 'error', 'idle'])

    def test_source_and_frozen_commands_and_cleanup(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen):
                voice = self.voice()
                process = MagicMock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                with patch.object(sys, 'frozen', frozen, create=True), patch('jarvis.voice.subprocess.Popen', return_value=process) as popen:
                    self.assertEqual(voice._speak_process('private words', 'openai'), 'completed')
                args = popen.call_args.args[0]
                self.assertNotIn('private words', args)
                self.assertEqual(args[1], '--jarvis-speech-worker' if frozen else '-m')
                self.assertFalse(Path(args[-1]).exists())
                self.assertIsNone(voice._process)

    def test_cancel_does_not_fall_back(self):
        voice = self.voice()
        with patch('jarvis.voice.settings', replace(settings, voice_engine='openai')), patch.object(voice, '_speak_process', return_value='interrupted'), patch.object(voice, '_speak_offline') as fallback:
            self.assertEqual(voice._play_text('hello'), 'interrupted')
        fallback.assert_not_called()

    def test_provider_failure_falls_back_offline(self):
        voice = self.voice()
        states = []
        voice.on_state_change = states.append
        with patch('jarvis.voice.settings', replace(settings, voice_engine='openai')), patch.object(voice, '_speak_process', return_value='failed'), patch.object(voice, '_speak_offline', return_value='completed'):
            self.assertEqual(voice._play_text('hello'), 'completed')
        self.assertIn('fallback', states)
        self.assertIn('offline', voice.last_error)

    def test_speed_controls_return_values_while_idle(self):
        voice = self.voice()
        self.assertEqual(voice.speed_up(), 1.1)
        self.assertEqual(voice.speed_down(), 1.0)
        self.assertEqual(voice.reset_speed(), 1.0)

    def test_muted_voice_never_enqueues(self):
        voice = self.voice()
        voice.mute()
        voice.speak('hello')
        self.assertTrue(voice._queue.empty())
        self.assertFalse(voice.play())

    def test_long_words_are_not_ids_because_of_later_number(self):
        word = 'electroencephalographically'
        self.assertIn(word, speechify(f'{word} measured 12 times'))

    def test_speech_chunks_preserve_text_and_bound_requests(self):
        for text in ['Hello. ' * 1000, 'नमस्ते ' * 1000, 'x' * 3000]:
            chunks = list(speech_chunks(text))
            self.assertTrue(all(0 < len(c) <= 1200 for c in chunks))
            self.assertEqual(''.join(''.join(chunks).split()), ''.join(text.split()))

    def test_openai_payload_has_style_and_bounded_timeout(self):
        config = replace(settings, openai_api_key='test-key', openai_tts_voice='coral', openai_tts_model='gpt-4o-mini-tts')
        with patch('jarvis.speech_worker.settings', config), patch('openai.OpenAI') as factory:
            render_openai('Hi Adib', Path('not-written.mp3'), 1.1)
        self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
        client = factory.return_value.__enter__.return_value
        payload = client.audio.speech.with_streaming_response.create.call_args.kwargs
        self.assertEqual(payload['voice'], 'coral')
        self.assertEqual(payload['speed'], 1.1)
        self.assertIn('warm', payload['instructions'])

    def test_legacy_tts_omits_unsupported_instructions(self):
        with patch('jarvis.speech_worker.settings', replace(settings, openai_api_key='test', openai_tts_model='tts-1')), patch('openai.OpenAI') as factory:
            render_openai('hello', Path('not-written.mp3'), 1)
        payload = factory.return_value.__enter__.return_value.audio.speech.with_streaming_response.create.call_args.kwargs
        self.assertNotIn('instructions', payload)

    def test_missing_speech_key_does_not_make_request(self):
        with patch('jarvis.speech_worker.settings', replace(settings, openai_api_key='')), patch('openai.OpenAI') as factory:
            with self.assertRaises(RuntimeError):
                render_openai('hello', Path('not-written.mp3'), 1)
        factory.assert_not_called()

    def test_offline_selects_installed_female_voice(self):
        engine = MagicMock()
        engine.getProperty.return_value = [SimpleNamespace(id='zira-id', name='Microsoft Zira', gender=None)]
        with patch('pyttsx3.init', return_value=engine), patch('jarvis.speech_worker.settings', replace(settings, offline_voice_id='')):
            speak_offline('hello', 1)
        engine.setProperty.assert_any_call('voice', 'zira-id')
        engine.stop.assert_called_once()

    def test_windows_sapi_fallback_uses_temp_file_not_spoken_command(self):
        with tempfile.TemporaryDirectory() as directory:
            text_path = Path(directory) / 'speech.txt'
            text_path.write_text('private spoken words', encoding='utf-8')
            completed = SimpleNamespace(returncode=0)
            with patch('jarvis.speech_worker.os.name', 'nt'), patch('jarvis.speech_worker.subprocess.run', return_value=completed) as run:
                speak_windows_sapi(text_path, 1.0)
        args = run.call_args.args[0]
        self.assertIn(str(text_path), args)
        self.assertNotIn('private spoken words', ' '.join(args))

    def test_offline_worker_uses_windows_sapi_after_pyttsx3_error(self):
        with tempfile.TemporaryDirectory() as directory:
            text_path = Path(directory) / 'speech.txt'
            text_path.write_text('hello', encoding='utf-8')
            with patch('jarvis.speech_worker.speak_offline', side_effect=RuntimeError('com bridge missing')), patch('jarvis.speech_worker.speak_windows_sapi') as sapi:
                self.assertEqual(speech_main(['--engine', 'pyttsx3', '--file', str(text_path)]), 0)
        sapi.assert_called_once_with(text_path, 1.0)

    def test_cancelled_microphone_does_not_open_device(self):
        event = threading.Event()
        event.set()
        with patch('jarvis.microphone._deps') as deps:
            self.assertEqual(record_until_silence(stop_event=event), '')
        deps.assert_not_called()

    def test_cancel_during_transcription_discards_result(self):
        event = threading.Event()
        sd = MagicMock()
        stream = sd.RawInputStream.return_value.__enter__.return_value
        stream.read.return_value = (b'\xe8\x03' * 480, False)
        def transcribe(*args):
            event.set()
            return 'unwanted command'
        with patch('jarvis.microphone._deps', return_value=(sd, MagicMock())), patch('jarvis.microphone._transcribe_pcm', side_effect=transcribe):
            self.assertEqual(record_until_silence(max_seconds=2, stop_event=event), '')

    def test_wake_listener_preserves_command_case(self):
        calls = []
        listener = WakeWordListener(lambda command: (calls.append(command), listener.stop()))
        with patch('jarvis.microphone.record_and_transcribe', return_value='Hey Jarvis Open MyFile.PY'):
            listener._loop()
        self.assertEqual(calls, ['Open MyFile.PY'])

    def test_stopped_wake_listener_discards_late_command(self):
        callback = MagicMock()
        listener = WakeWordListener(callback)
        def record(*args):
            listener.stop()
            return 'hey jarvis open app'
        with patch('jarvis.microphone.record_and_transcribe', side_effect=record):
            listener._loop()
        callback.assert_not_called()


class SpeechProcessIntegrationTests(unittest.TestCase):
    def test_desktop_dispatch_exits_without_starting_gui(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'desktop_app.py'),
                                 '--jarvis-speech-worker', '--help'],
                                cwd=root, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--engine', result.stdout)

    @unittest.skipIf(os.name == 'nt', 'POSIX process group integration; Windows uses taskkill')
    def test_stop_reaps_real_child_process(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                   start_new_session=True)
        try:
            VoiceOutput._terminate_process(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
