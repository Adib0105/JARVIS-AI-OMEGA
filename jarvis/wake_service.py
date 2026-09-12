"""Opt-in, local-only wake detection. Never uploads ambient microphone audio."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path


def split_wake(text: str, wake_word: str = 'jarvis') -> str | None:
    aliases = {wake_word.strip(), 'jarvis', 'jarves', 'जार्विस', 'जारविस'} - {''}
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(x) for x in sorted(aliases, key=len, reverse=True)) + r')(?!\w)'
    match = re.search(pattern, text, re.IGNORECASE)
    return text[match.end():].strip(' ,.!?।') if match else None


class BackgroundWakeListener:
    def __init__(self, model_path, on_wake, on_error, suspended=lambda: False, wake_word='jarvis'):
        self.model_path = model_path
        self.on_wake, self.on_error = on_wake, on_error
        self.suspended, self.wake_word = suspended, wake_word
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def start(self):
        if self._thread and self._thread.is_alive():
            raise RuntimeError('Listener is stopping. Please retry in a moment.')
        if not self.model_path.strip() or not Path(self.model_path).expanduser().is_dir():
            raise RuntimeError('Select an extracted Vosk model folder in Background / Weather first.')
        # Fail before hiding the window if optional dependencies are absent.
        import vosk  # noqa: F401
        import sounddevice  # noqa: F401
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='jarvis-background-wake')
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        try:
            import vosk
            import sounddevice as sd
            from .microphone import _exclusive_stream, input_device
            model = vosk.Model(str(Path(self.model_path).expanduser().resolve()))
            recognizer = vosk.KaldiRecognizer(model, 16000)
            with _exclusive_stream(sd, samplerate=16000, blocksize=1600, dtype='int16', channels=1, device=input_device()) as stream:
                while not self._stop.is_set():
                    data, overflowed = stream.read(1600)
                    if self._stop.is_set():
                        break
                    if self.suspended() or overflowed:
                        recognizer.Reset()
                        continue
                    if recognizer.AcceptWaveform(bytes(data)):
                        command = split_wake(json.loads(recognizer.Result()).get('text', ''), self.wake_word)
                        if command is not None and not self._stop.is_set() and not self.suspended():
                            self.on_wake(command)
                            recognizer.Reset()
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(str(exc))
        finally:
            self._stop.set()
