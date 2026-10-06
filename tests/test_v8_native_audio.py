"""Real spawn/kill/reap behavior with synthetic native-device/recognizer workers.

No physical microphone, Bluetooth, Windows resume or audible output is claimed.
"""
import multiprocessing
import os
import threading
import time
import unittest
from unittest.mock import patch

from jarvis.native_audio import (AudioCancelled, NativeAudioCapture, NativeWorker,
                                 LocalVoskTranscriber, transcribe_in_process)


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
