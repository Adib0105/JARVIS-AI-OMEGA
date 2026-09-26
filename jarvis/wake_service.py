"""Opt-in, local-only wake detection. Never uploads ambient microphone audio."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path


def split_wake(text: str, wake_word: str = 'jarvis') -> str | None:
    # Vosk commonly produces small phonetic variations for the product name on
    # Indian-English microphones.  Keep the aliases deliberately bounded: we
    # accept a few close names and complete activation phrases, but never use a
    # broad fuzzy match that could turn ordinary room speech into a command.
    aliases = {
        wake_word.strip(),
        'wake up jarvis', 'wake jarvis', 'hey jarvis', 'hello jarvis',
        'okay jarvis', 'ok jarvis', 'jarvis', 'jarves', 'jervis', 'jarvish',
        'जार्विस', 'जारविस',
    } - {''}
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(x) for x in sorted(aliases, key=len, reverse=True)) + r')(?!\w)'
    match = re.search(pattern, text, re.IGNORECASE)
    return text[match.end():].strip(' ,.!?।') if match else None


class PartialWakeDetector:
    """Stable bare wake phrases can acknowledge before the final ASR endpoint.

    Text with an inline command is reserved for the final result, preserving it.
    """
    def __init__(self, wake_word, clock=time.monotonic):
        self.wake_word, self.clock = wake_word, clock
        self.reset()

    def reset(self):
        self.text, self.since, self.emitted = '', 0.0, False

    def feed(self, text, final=False):
        command = split_wake(text, self.wake_word)
        if final:
            result = None if self.emitted else command
            self.reset()
            return result
        if self.emitted:
            return None
        if command != '':
            self.text, self.since = '', 0.0
            return None
        normalized = text.strip().lower()
        now = self.clock()
        if normalized != self.text:
            self.text, self.since = normalized, now
        elif now - self.since >= 0.45:
            self.emitted = True
            return ''
        return None


class BackgroundWakeListener:
    def __init__(self, model_path, on_wake, on_error, suspended=lambda: False, wake_word='jarvis'):
        self.model_path = model_path
        self.on_wake, self.on_error = on_wake, on_error
        self.suspended, self.wake_word = suspended, wake_word
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._stream_lock = threading.RLock()
        self._stream = None
        self._thread = None
        self._startup_error = ''
        self.ready_at = 0.0
        self.last_heard_at = 0.0

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def ready(self):
        return bool(self.running and self._ready.is_set() and not self._startup_error)

    @property
    def startup_error(self):
        return self._startup_error

    def start(self, timeout=12.0):
        if self._thread and self._thread.is_alive():
            if self._stop.is_set():
                self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError('Listener is stopping. Please retry in a moment.')
        if not self.model_path.strip() or not Path(self.model_path).expanduser().is_dir():
            raise RuntimeError('Select an extracted Vosk model folder in Background / Weather first.')
        # Fail before hiding the window if optional dependencies are absent.
        import vosk  # noqa: F401
        import sounddevice  # noqa: F401
        self._stop.clear()
        self._ready.clear()
        self._startup_error = ''
        self.ready_at = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True, name='jarvis-background-wake')
        self._thread.start()

        # Do not claim that background listening is ON until the model is loaded
        # and PortAudio has actually opened the input device.  This bounded wait
        # also turns asynchronous startup failures into an actionable UI error.
        timeout = max(1.0, min(float(timeout), 30.0))
        if not self._ready.wait(timeout):
            self.stop(wait=True)
            raise RuntimeError('Microphone did not become ready in time. Check Windows microphone privacy and the selected input device.')
        if self._startup_error:
            message = self._startup_error
            self.stop(wait=True)
            raise RuntimeError(message)
        if not self.running:
            raise RuntimeError('Background microphone stopped before it became ready.')
        return True

    def stop(self, *, wait=False, timeout=3.0):
        self._stop.set()
        # PortAudio reads normally return every 100 ms.  Abort as a defensive
        # escape hatch for a disconnected/stalled Windows device so recovery can
        # restart instead of being stuck behind a live listener thread.
        with self._stream_lock:
            stream = self._stream
        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass
        thread = self._thread
        if wait and thread and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=max(0.1, min(float(timeout), 10.0)))
        return not bool(thread and thread.is_alive())

    def _loop(self):
        try:
            import vosk
            import sounddevice as sd
            from .microphone import _exclusive_stream, input_device
            from .offline_speech import get_vosk_model
            model = get_vosk_model(self.model_path)
            detector = PartialWakeDetector(self.wake_word)
            recognizer = vosk.KaldiRecognizer(model, 16000)
            with _exclusive_stream(sd, samplerate=16000, blocksize=1600, dtype='int16', channels=1, device=input_device()) as stream:
                with self._stream_lock:
                    self._stream = stream
                self.ready_at = time.time()
                self._ready.set()
                while not self._stop.is_set():
                    data, overflowed = stream.read(1600)
                    if self._stop.is_set():
                        break
                    if self.suspended() or overflowed:
                        recognizer.Reset()
                        detector.reset()
                        continue
                    final = bool(recognizer.AcceptWaveform(bytes(data)))
                    raw = recognizer.Result() if final else recognizer.PartialResult()
                    decoded = json.loads(raw)
                    text = decoded.get('text' if final else 'partial', '')
                    command = detector.feed(text, final) if isinstance(text, str) else None
                    if command is not None and not self._stop.is_set() and not self.suspended():
                        self.last_heard_at = time.time()
                        self.on_wake(command)
                        recognizer.Reset()
        except Exception as exc:
            self._startup_error = str(exc)
            self._ready.set()
            if not self._stop.is_set():
                self.on_error(str(exc))
        finally:
            with self._stream_lock:
                self._stream = None
            self._ready.set()
            self._stop.set()
