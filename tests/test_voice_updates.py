from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from jarvis.config import settings
from jarvis.voice_profiles import load_profile, save_profile, profile_overrides
from jarvis.voice import VoiceOutput
from jarvis.voice_diagnostics import diagnose_voice
from jarvis import offline_speech, microphone


class VoiceProfileTests(unittest.TestCase):
    def test_profile_round_trip_contains_no_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prefs.json'
            save_profile(path, 'gentle')
            self.assertEqual(load_profile(path), 'gentle')
            self.assertEqual(json.loads(path.read_text()), {'profile': 'gentle'})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_corrupt_and_unknown_preferences_use_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prefs.json'
            for contents in ('{bad', '[]', '{"profile": "unknown"}', '{"profile": []}', 'x' * 5000):
                path.write_text(contents)
                self.assertEqual(load_profile(path), 'configured')

    def test_unknown_profile_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prefs.json'
            save_profile(path, 'offline')
            with self.assertRaises(ValueError):
                save_profile(path, '../../bad')
            self.assertEqual(load_profile(path), 'offline')

    def test_runtime_profile_reaches_child_process(self):
        with tempfile.TemporaryDirectory() as directory:
            config = replace(settings, db_path=Path(directory) / 'db', enable_voice_output=False)
            with patch('jarvis.voice.settings', config):
                voice = VoiceOutput()
                voice.set_profile('offline')
                self.assertEqual(voice.engine, 'pyttsx3')
                voice._active_epoch = voice._cancel_epoch
                voice._interrupt_reason = None
                process = MagicMock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                with patch('jarvis.voice.subprocess.Popen', return_value=process) as popen:
                    voice._speak_process('hello', voice.engine)
                self.assertEqual(popen.call_args.kwargs['env']['VOICE_ENGINE'], 'pyttsx3')
                self.assertEqual(VoiceOutput().profile, 'offline')
                voice.shutdown()

    def test_profile_copy_cannot_mutate_global_defaults(self):
        first = profile_overrides('gentle')
        first['VOICE_ENGINE'] = 'bad'
        self.assertEqual(profile_overrides('gentle')['VOICE_ENGINE'], 'edge')


class OfflineRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.saved = offline_speech._model, offline_speech._model_path
        offline_speech._model = offline_speech._model_path = None
        self.addCleanup(self.restore)

    def restore(self):
        offline_speech._model, offline_speech._model_path = self.saved

    def test_offline_segments_and_final_text_preserved(self):
        vosk = MagicMock()
        rec = vosk.KaldiRecognizer.return_value
        rec.AcceptWaveform.side_effect = [True, False]
        rec.Result.return_value = '{"text":"hello adib"}'
        rec.FinalResult.return_value = '{"text":"how are you"}'
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'vosk': vosk}):
            result = offline_speech.transcribe_vosk(b'\0\0' * 6000, 16000, directory)
        self.assertEqual(result, 'hello adib how are you')
        self.assertEqual(vosk.Model.call_count, 1)

    def test_model_is_reused_without_language_auto_download(self):
        vosk = MagicMock()
        vosk.KaldiRecognizer.return_value.FinalResult.return_value = '{"text":""}'
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {'vosk': vosk}):
            offline_speech.transcribe_vosk(b'', 16000, directory)
            offline_speech.transcribe_vosk(b'', 16000, directory)
            vosk.Model.assert_called_once_with(str(Path(directory).resolve()))

    def test_missing_path_does_not_load_or_download_model(self):
        with patch.dict(sys.modules, {'vosk': MagicMock()}) as modules:
            with self.assertRaises(RuntimeError):
                offline_speech.transcribe_vosk(b'\0\0', 16000, '')
            modules['vosk'].Model.assert_not_called()

    def test_invalid_pcm_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                offline_speech.transcribe_vosk(b'odd', 16000, directory)

    def test_offline_failure_never_calls_cloud_recognizer(self):
        with patch('jarvis.microphone.settings', replace(settings, speech_engine='vosk')), patch('jarvis.offline_speech.transcribe_vosk', side_effect=RuntimeError('model missing')), patch('jarvis.microphone._deps') as cloud:
            with self.assertRaises(RuntimeError):
                microphone._transcribe_pcm(b'\0\0', 16000, 'hi-IN')
            cloud.assert_not_called()

    def test_offline_capture_does_not_require_speechrecognition(self):
        with patch('jarvis.microphone.settings', replace(settings, speech_engine='vosk')), patch.dict(sys.modules, {'sounddevice': MagicMock(), 'speech_recognition': None}):
            sd, sr = microphone._deps()
            self.assertIsNotNone(sd)
            self.assertIsNone(sr)

    def test_device_id_name_and_default(self):
        for raw, expected in [('2', 2), ('USB microphone', 'USB microphone'), ('', None)]:
            with patch('jarvis.microphone.settings', replace(settings, mic_device=raw)):
                self.assertEqual(microphone.input_device(), expected)

    def test_capture_lock_blocks_overlap_and_releases_after_failure(self):
        sd = MagicMock()
        with microphone._exclusive_stream(sd):
            with self.assertRaises(microphone.MicrophoneUnavailable):
                with microphone._exclusive_stream(sd):
                    pass
        sd.RawInputStream.side_effect = RuntimeError('device failed')
        with self.assertRaises(RuntimeError):
            with microphone._exclusive_stream(sd):
                pass
        self.assertFalse(microphone._CAPTURE_LOCK.locked())

    def test_rapid_wake_restart_does_not_clear_old_stop(self):
        listener = microphone.WakeWordListener(lambda _: None)
        listener._thread = MagicMock()
        listener._thread.is_alive.return_value = True
        listener.stop()
        with patch('jarvis.microphone.threading.Thread') as factory:
            listener.start()
        factory.assert_not_called()
        self.assertTrue(listener._stop.is_set())


class VoiceDoctorTests(unittest.TestCase):
    def test_diagnostics_never_record_or_reveal_api_key(self):
        sd = MagicMock()
        sd.query_devices.return_value = [{'name': 'USB mic', 'max_input_channels': 1}]
        with patch.dict(sys.modules, {'sounddevice': sd}), patch('jarvis.voice_diagnostics.importlib.util.find_spec', return_value=object()):
            report = diagnose_voice('premium', replace(settings, openai_api_key='SECRET-MUST-NOT-LEAK'))
        self.assertNotIn('SECRET-MUST-NOT-LEAK', json.dumps(report))
        sd.RawInputStream.assert_not_called()
        self.assertEqual(report['input_devices'][0]['id'], 0)

    def test_offline_report_marks_both_audio_paths_local(self):
        with patch.dict(sys.modules, {'sounddevice': None}):
            report = diagnose_voice('offline', replace(settings, speech_engine='vosk'))
        self.assertFalse(report['speech_output_uses_network'])
        self.assertFalse(report['recognition_uses_network'])

    def test_doctor_runs_without_cloud_key_or_gui(self):
        result = subprocess.run([sys.executable, '-m', 'jarvis.voice_diagnostics'], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('checks', json.loads(result.stdout))


class DesktopErrorCallbacksTests(unittest.TestCase):
    def test_background_errors_survive_exception_scope(self):
        from jarvis.gui import JarvisDesktop
        desktop = MagicMock()
        callbacks = []
        desktop.root.after.side_effect = lambda delay, callback: callbacks.append(callback)
        desktop.jarvis.chat.side_effect = RuntimeError('chat failed')
        JarvisDesktop._answer_worker(desktop, 'hello', [])
        callbacks.pop()()
        desktop._answer_done.assert_called_once_with('', 'chat failed', False)
        desktop.jarvis.run_mission.side_effect = RuntimeError('mission failed')
        JarvisDesktop._mission_worker(desktop, 'goal')
        callbacks.pop()()
        desktop._mission_done.assert_called_once_with('', 'mission failed')
        with patch('jarvis.gui.record_and_transcribe', side_effect=RuntimeError('mic failed')):
            JarvisDesktop._mic_worker(desktop)
        callbacks.pop()()
        desktop._mic_done.assert_called_once_with('', 'mic failed')
        with patch('jarvis.gui.capture_screen', side_effect=RuntimeError('vision failed')):
            JarvisDesktop._vision_worker(desktop, 'what is this')
        callbacks.pop()()
        desktop._vision_done.assert_called_once_with('', '', 'vision failed')
