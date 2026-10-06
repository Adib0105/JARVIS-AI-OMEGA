"""Real spawn/kill/reap behavior with synthetic native-device/recognizer workers.

No physical microphone, Bluetooth, Windows resume or audible output is claimed.
"""
import multiprocessing
import json
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.native_audio import (AudioCancelled, NativeAudioCapture, NativeWorker,
                                 NativeWakeRecognizer, LocalVoskTranscriber, transcribe_in_process)


def stalled(pipe):
    pipe.send_bytes(b'R')
    time.sleep(60)


def device_error(pipe):
    pipe.send_bytes(b'Epermission denied')
    pipe.close()


def normal_device(pipe, parameters):
    pipe.send_bytes(b'R')
    pipe.send_bytes(b'D\0' + b'\0\0' * parameters['blocksize'])
    pipe.send_bytes(b'D\1' + b'\0\0' * parameters['blocksize'])
    time.sleep(60)


def partial_device(pipe, parameters):
    pipe.send_bytes(b'R')
    pipe.send_bytes(b'D\0short')
    time.sleep(60)


def crashing(pipe):
    os._exit(17)


def oversized(pipe):
    pipe.send_bytes(b'x'*70000)


def recognize_ok(*_):
    return 'heard clearly'


def recognize_stalled(*_):
    time.sleep(60)
    return 'late command'


def recognize_exit(*_):
    raise SystemExit('recognizer stopped')


def wake_fixture(pipe, model_path):
    # The production byte protocol and process boundary run unchanged; only the
    # unavailable native model is synthetic. No real voice accuracy is claimed.
    from jarvis.native_audio import _wake_worker
    class Recognizer:
        def __init__(self, *_):
            if model_path == 'stall-model':
                time.sleep(60)
            self.frames = 0
        def AcceptWaveform(self, data):
            if data[0] == 4:
                time.sleep(60)
            self.frames += 1
            self.large = data[0] == 3
            return data[0] != 1
        def Result(self):
            return json.dumps({'text': 'x'*20000 if self.large else f'Jarvis Write {{ENTER}} café {self.frames}'})
        def PartialResult(self):
            return json.dumps({'partial': 'Jarvis'})
        def Reset(self):
            if model_path == 'stall-reset':
                time.sleep(60)
            self.frames = 0
    with patch.dict('sys.modules', {'vosk': SimpleNamespace(KaldiRecognizer=Recognizer)}), patch('jarvis.offline_speech.get_vosk_model', return_value=object()):
        _wake_worker(pipe, model_path)


def malformed_wake(pipe, _model):
    pipe.send_bytes(b'R')
    pipe.recv_bytes(maxlength=3201)
    pipe.send_bytes(b'Xuntrusted result')
    time.sleep(60)


class NativeAudioProcessTests(unittest.TestCase):
    def assert_reaped(self, pid):
        self.assertNotIn(pid, [p.pid for p in multiprocessing.active_children()])

    def test_stalled_native_read_is_killed_and_reaped(self):
        worker = NativeWorker(stalled).start()
        self.addCleanup(worker.close)
        pid = worker.process.pid
        self.assertEqual(worker.receive(5), b'R')
        with self.assertRaises(TimeoutError):
            worker.receive(.1)
        started = time.monotonic()
        worker.close()
        self.assertLess(time.monotonic()-started, 2)
        self.assert_reaped(pid)

    def test_repeated_abort_is_nonblocking_and_new_owner_can_start(self):
        for _ in range(3):
            worker = NativeWorker(stalled).start()
            self.addCleanup(worker.close)
            pid = worker.process.pid
            self.assertEqual(worker.receive(5), b'R')
            start = time.monotonic()
            for _ in range(20):
                worker.abort()
            self.assertLess(time.monotonic()-start, .2)
            with self.assertRaises(AudioCancelled):
                worker.receive(1)
            worker.close()
            self.assert_reaped(pid)

    def test_worker_crash_and_permission_denial_are_explicit(self):
        for target in (crashing, device_error):
            worker = NativeWorker(target).start()
            self.addCleanup(worker.close)
            pid = worker.process.pid
            with self.assertRaises(RuntimeError):
                worker.receive(5)
            worker.close()
            self.assert_reaped(pid)

    def test_oversized_ipc_is_rejected_and_reaped(self):
        worker = NativeWorker(oversized).start()
        self.addCleanup(worker.close)
        pid = worker.process.pid
        with self.assertRaises(RuntimeError):
            worker.receive(5, limit=1024)
        worker.close()
        self.assert_reaped(pid)

    def test_capture_ready_framing_overflow_and_cleanup(self):
        with patch('jarvis.native_audio._capture_worker', normal_device):
            capture = NativeAudioCapture(blocksize=16)
        with capture as stream:
            pid = stream.worker.process.pid
            self.assertEqual(stream.read(16), (b'\0\0'*16, False))
            self.assertEqual(stream.read(16), (b'\0\0'*16, True))
        self.assert_reaped(pid)

    def test_partial_frame_is_never_used_as_command_audio(self):
        with patch('jarvis.native_audio._capture_worker', partial_device):
            capture = NativeAudioCapture(blocksize=16)
        with capture as stream:
            with self.assertRaisesRegex(RuntimeError, 'Invalid microphone frame'):
                stream.read(16)

    def test_asr_timeout_kills_worker_and_recovers(self):
        with self.assertRaises(TimeoutError):
            transcribe_in_process(recognize_stalled, b'\0\0', 16000, 'en', None, timeout=.2)
        self.assertEqual(transcribe_in_process(recognize_ok, b'\0\0', 16000, 'en', None), 'heard clearly')
        self.assertFalse([p for p in multiprocessing.active_children() if p.name == 'jarvis-native-audio'])

    def test_cancelled_asr_drops_late_result_and_reaps(self):
        cancel = threading.Event()
        timer = threading.Timer(.2, cancel.set)
        timer.start()
        self.addCleanup(timer.join)
        self.assertEqual(transcribe_in_process(recognize_stalled, b'\0\0', 16000, 'en', cancel), '')
        self.assertFalse([p for p in multiprocessing.active_children() if p.name == 'jarvis-native-audio'])

    def test_asr_exit_is_error_and_precancel_never_spawns(self):
        with self.assertRaisesRegex(RuntimeError, 'SystemExit'):
            transcribe_in_process(recognize_exit, b'\0\0', 16000, 'en', None)
        cancel = threading.Event(); cancel.set()
        with patch('jarvis.native_audio.NativeWorker.start') as start:
            self.assertEqual(transcribe_in_process(recognize_ok, b'\0\0', 16000, 'en', cancel), '')
            start.assert_not_called()

    def test_production_recognizers_use_process_boundary_and_keep_ownership(self):
        from jarvis import microphone
        for recognizer in (microphone._transcribe_pcm, LocalVoskTranscriber('local-model')):
            def run(*_):
                self.assertTrue(microphone._ASR_LOCK.locked())
                return 'recognized'
            with patch('jarvis.native_audio.transcribe_in_process', side_effect=run) as isolate:
                self.assertEqual(microphone._bounded_transcribe(recognizer, b'\0\0', 16000, 'en', None), 'recognized')
                isolate.assert_called_once()
            self.assertFalse(microphone._ASR_LOCK.locked())

    def test_capture_start_failure_releases_pipe_handles(self):
        import multiprocessing.process
        worker = NativeWorker(stalled)
        with patch.object(multiprocessing.process.BaseProcess, 'start', side_effect=OSError('cannot start')):
            with self.assertRaises(OSError):
                worker.start()
        self.assertIsNone(worker.process)
        self.assertIsNone(worker.reader)

    def wake_recognizer(self, model='fixture', **kwargs):
        with patch('jarvis.native_audio._wake_worker', wake_fixture):
            return NativeWakeRecognizer(model, threading.Event(), startup_timeout=10, **kwargs)

    def test_wake_process_preserves_final_unicode_and_acknowledges_reset(self):
        with self.wake_recognizer() as recognizer:
            pid = recognizer.worker.process.pid
            self.assertEqual(recognizer.feed(b'\1'*3200), (False, 'Jarvis'))
            self.assertEqual(recognizer.feed(b'\2'*3200), (True, 'Jarvis Write {ENTER} café 2'))
            recognizer.reset()
            self.assertEqual(recognizer.feed(b'\2'*3200), (True, 'Jarvis Write {ENTER} café 1'))
        self.assert_reaped(pid)

    def test_wake_native_model_loading_is_cancellable_and_reaped(self):
        recognizer = self.wake_recognizer('stall-model')
        timer = threading.Timer(.2, recognizer.stop_event.set)
        timer.start()
        self.addCleanup(timer.join)
        started = time.monotonic()
        with self.assertRaises(AudioCancelled), recognizer:
            self.fail('A stalled model must never report ready')
        self.assertLess(time.monotonic()-started, 3)
        self.assertIsNone(recognizer.worker.process)

    def test_wake_inference_and_reset_stalls_are_reaped_and_restart_recovers(self):
        for model, operation in [('fixture', lambda r: r.feed(b'\4'*3200)),
                                 ('stall-reset', lambda r: r.reset())]:
            with self.subTest(model=model):
                recognizer = self.wake_recognizer(model, timeout=.1)
                with self.assertRaises(TimeoutError), recognizer:
                    pid = recognizer.worker.process.pid
                    operation(recognizer)
                self.assert_reaped(pid)
        with self.wake_recognizer() as recognizer:
            self.assertTrue(recognizer.feed(b'\2'*3200)[0])

    def test_wake_invalid_or_oversized_frames_cannot_become_commands(self):
        with self.wake_recognizer() as recognizer:
            for bad in (b'short', b'\0'*3202, 'text'):
                with self.assertRaises(ValueError):
                    recognizer.feed(bad)
            with self.assertRaisesRegex(RuntimeError, 'oversized'):
                recognizer.feed(b'\3'*3200)
        with patch('jarvis.native_audio._wake_worker', malformed_wake):
            recognizer = NativeWakeRecognizer('fixture', threading.Event(), startup_timeout=10)
        with recognizer, self.assertRaisesRegex(RuntimeError, 'Invalid wake'):
            recognizer.feed(b'\0'*3200)

    def test_background_stop_cancels_native_inference_without_late_dispatch(self):
        from jarvis.wake_service import BackgroundWakeListener
        listener = BackgroundWakeListener('fixture', MagicMock(), MagicMock())
        stream = MagicMock()
        stream.read.return_value = (b'\4'*3200, False)
        stream.__enter__.return_value = stream
        entered = threading.Event()
        original_feed = NativeWakeRecognizer.feed
        def feed(recognizer, data):
            entered.set()
            return original_feed(recognizer, data)
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}), patch('jarvis.microphone._exclusive_stream', return_value=stream), patch('jarvis.native_audio._wake_worker', wake_fixture), patch.object(NativeWakeRecognizer, 'feed', feed):
            listener._thread = threading.Thread(target=listener._loop)
            listener._thread.start()
            try:
                self.assertTrue(entered.wait(10))
                self.assertTrue(listener.stop(wait=True, timeout=3))
                listener.on_wake.assert_not_called()
                listener.on_error.assert_not_called()
            finally:
                listener.stop(wait=True)
        self.assertFalse([p for p in multiprocessing.active_children() if p.name == 'jarvis-native-audio'])
