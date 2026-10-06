"""Killable native audio workers. These trusted workers are not code sandboxes.

Use spawn (including Windows frozen freeze_support), one owner per pipe, bounded
byte messages, and close/reap before releasing microphone/ASR ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
import multiprocessing
import os
import sys
import threading
import time

from .security.redaction import redact_text

_ORPHANS = []
_ORPHAN_LOCK = threading.Lock()


class AudioCancelled(RuntimeError):
    pass


def _parent_watchdog():
    parent = multiprocessing.parent_process()
    if parent is None:
        return
    def watch():
        while parent.is_alive():
            time.sleep(.25)
        os._exit(75)
    threading.Thread(target=watch, name='audio-parent-watchdog', daemon=True).start()


def _capture_worker(pipe, parameters):
    _parent_watchdog()
    try:
        import sounddevice as sd
        with sd.RawInputStream(**parameters) as stream:
            pipe.send_bytes(b'R')  # Ready only after the OS device has opened.
            while True:
                audio, overflow = stream.read(parameters['blocksize'])
                raw = bytes(audio)
                if len(raw) != parameters['blocksize'] * 2:
                    raise RuntimeError('Unexpected microphone frame size.')
                pipe.send_bytes(b'D' + bytes([bool(overflow)]) + raw)
    except BaseException as exc:
        try:
            pipe.send_bytes(b'E' + redact_text(f'{type(exc).__name__}: {exc}').encode('utf-8')[:2048])
        except (OSError, EOFError):
            pass
    finally:
        pipe.close()


def _transcribe_worker(pipe, recognize, data, rate, language):
    _parent_watchdog()
    try:
        text = str(recognize(data, rate, language)).encode('utf-8')
        if len(text) > 16000:
            raise RuntimeError('Recognition result exceeded the transcript limit.')
        pipe.send_bytes(b'T' + text)
    except BaseException as exc:
        try:
            pipe.send_bytes(b'E' + redact_text(f'{type(exc).__name__}: {exc}').encode('utf-8')[:2048])
        except (OSError, EOFError):
            pass
    finally:
        pipe.close()


class NativeWorker:
    def __init__(self, target, args=()):
        self.target, self.args = target, args
        self.process = self.reader = None
        self.cancel = threading.Event()

    def start(self):
        if getattr(sys, 'frozen', False) and os.name != 'nt':
            raise RuntimeError('Native audio spawn workers are supported in source installs and Windows packages only.')
        with _ORPHAN_LOCK:
            for process in tuple(_ORPHANS):
                if process.is_alive():
                    process.kill()
                    process.join(.5)
                if process.is_alive():
                    raise RuntimeError('Previous native audio worker has not exited; restart is blocked.')
                process.close()
                _ORPHANS.remove(process)
        if self.cancel.is_set():
            raise AudioCancelled('Audio capture cancelled.')
        context = multiprocessing.get_context('spawn')
        self.reader, writer = context.Pipe(duplex=False)
        self.process = context.Process(target=self.target, args=(writer, *self.args), daemon=True,
                                       name='jarvis-native-audio')
        try:
            self.process.start()
        except BaseException:
            self.reader.close()
            self.process.close()
            self.reader = self.process = None
            raise
        finally:
            writer.close()
        return self

    def receive(self, timeout, *, cancel=None, limit=65536):
        deadline = time.monotonic() + timeout
        while True:
            if self.cancel.is_set() or (cancel is not None and cancel.is_set()):
                raise AudioCancelled('Audio capture/recognition cancelled.')
            if time.monotonic() >= deadline:
                raise TimeoutError('Native audio worker timed out; reconnect/select the input device and retry.')
            if self.reader.poll(.025):
                try:
                    message = self.reader.recv_bytes(maxlength=limit)
                except (EOFError, OSError) as exc:
                    raise RuntimeError('Native audio worker stopped or sent an invalid frame.') from exc
                if self.cancel.is_set() or (cancel is not None and cancel.is_set()):
                    raise AudioCancelled('Audio capture/recognition cancelled.')
                if message[:1] == b'E':
                    raise RuntimeError(message[1:].decode('utf-8', 'replace'))
                return message
            if not self.process.is_alive():
                raise RuntimeError('Native audio worker exited before returning a result.')

    def abort(self):
        # UI-safe: the owning read loop performs bounded termination/reaping.
        self.cancel.set()

    def close(self):
        self.abort()
        process, self.process = self.process, None
        try:
            if process is not None:
                if process.is_alive():
                    process.terminate()
                process.join(.5)
                if process.is_alive():
                    process.kill()
                    process.join(.5)
                if process.is_alive():
                    with _ORPHAN_LOCK:
                        _ORPHANS.append(process)
                    raise RuntimeError('Native audio process termination could not be confirmed.')
                process.close()
        finally:
            if self.reader is not None:
                self.reader.close()
                self.reader = None


class NativeAudioCapture:
    def __init__(self, *, samplerate=16000, blocksize=480, dtype='int16', channels=1, device=None):
        if (type(blocksize) is not int or not 1 <= blocksize <= 16000
                or type(samplerate) is not int or not 8000 <= samplerate <= 48000
                or dtype != 'int16' or channels != 1
                or not (device is None or type(device) in (str, int))):
            raise ValueError('Only bounded mono int16 microphone input is supported.')
        self.blocksize = blocksize
        self.worker = NativeWorker(_capture_worker, ({'samplerate': samplerate, 'blocksize': blocksize,
                                   'dtype': dtype, 'channels': channels, 'device': device},))

    def __enter__(self):
        try:
            self.worker.start()
            if self.worker.receive(5) != b'R':
                raise RuntimeError('Microphone readiness was not confirmed.')
        except BaseException:
            self.worker.close()
            raise
        return self

    def read(self, frames):
        if frames != self.blocksize:
            raise ValueError('Microphone read size must match the configured block size.')
        message = self.worker.receive(2)
        if message[:1] != b'D' or len(message) != 2 + self.blocksize*2 or message[1] not in (0, 1):
            raise RuntimeError('Invalid microphone frame; input was discarded.')
        return message[2:], bool(message[1])

    def abort(self):
        self.worker.abort()

    def __exit__(self, *_):
        self.worker.close()


@dataclass(frozen=True)
class LocalVoskTranscriber:
    model_path: str

    def __call__(self, data, sample_rate, _language):
        from .offline_speech import transcribe_vosk
        return transcribe_vosk(data, sample_rate, self.model_path)


def transcribe_in_process(recognize, data, rate, language, stop_event, *, timeout=18):
    if len(data) > 3_000_000 or len(data) % 2 or not 8000 <= rate <= 48000:
        raise ValueError('Recognition input exceeds the bounded mono PCM contract.')
    if stop_event is not None and stop_event.is_set():
        return ''
    worker = NativeWorker(_transcribe_worker, (recognize, data, rate, language))
    try:
        worker.start()
        message = worker.receive(timeout, cancel=stop_event, limit=16001)
        if message[:1] != b'T':
            raise RuntimeError('Recognition result could not be validated.')
        return message[1:].decode('utf-8')
    except AudioCancelled:
        return ''
    finally:
        worker.close()


def _smoke_worker(pipe):
    """Trusted non-recording probe for the frozen multiprocessing entry point."""
    pipe.send_bytes(b'R')
    time.sleep(30)


def worker_selfcheck():
    worker = NativeWorker(_smoke_worker)
    try:
        worker.start()
        if worker.receive(10) != b'R':
            return 1
    finally:
        worker.close()
    return 0
