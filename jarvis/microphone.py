from __future__ import annotations

import threading
import time
from typing import Callable


class MicrophoneUnavailable(RuntimeError):
    pass


def _deps():
    try:
        import sounddevice as sd
        import speech_recognition as sr
    except Exception as exc:
        raise MicrophoneUnavailable(
            'Optional microphone packages are not available. Run setup_windows.ps1 again to install '
            'sounddevice and SpeechRecognition.'
        ) from exc
    return sd, sr


def record_and_transcribe(
    duration: float = 6.0,
    language: str = 'en-IN',
    sample_rate: int = 16000,
) -> str:
    """Record a short mono PCM clip and transcribe it with SpeechRecognition's Google recognizer."""
    sd, sr = _deps()
    duration = max(1.0, min(float(duration), 20.0))
    frames = int(sample_rate * duration)

    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=0,
            dtype='int16',
            channels=1,
        ) as stream:
            data, overflowed = stream.read(frames)
    except Exception as exc:
        raise MicrophoneUnavailable(f'Microphone recording failed: {exc}') from exc

    if overflowed:
        # Overflow does not always make the clip unusable; continue and let recognition decide.
        pass

    recognizer = sr.Recognizer()
    audio = sr.AudioData(bytes(data), sample_rate, 2)
    try:
        return recognizer.recognize_google(audio, language=language).strip()
    except sr.UnknownValueError as exc:
        raise RuntimeError('Voice clear nahi samajh aayi. Dobara thoda clearly bolo.') from exc
    except sr.RequestError as exc:
        raise RuntimeError(f'Speech recognition service unavailable: {exc}') from exc


class WakeWordListener:
    """Optional explicit wake-word loop. It never starts unless the user enables it."""

    def __init__(
        self,
        on_command: Callable[[str], None],
        on_state: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        wake_word: str = 'hey jarvis',
        language: str = 'en-IN',
        chunk_seconds: float = 3.5,
    ) -> None:
        self.on_command = on_command
        self.on_state = on_state or (lambda _state: None)
        self.on_error = on_error or (lambda _message: None)
        self.wake_word = wake_word.strip().lower() or 'hey jarvis'
        self.language = language
        self.chunk_seconds = max(2.0, min(chunk_seconds, 8.0))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='jarvis-wake-word')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        self.on_state('wake-idle')
        while not self._stop.is_set():
            try:
                heard = record_and_transcribe(self.chunk_seconds, self.language)
                lower = heard.lower()
                if self.wake_word not in lower:
                    continue

                self.on_state('listening')
                after = lower.split(self.wake_word, 1)[1].strip(' ,.!?')
                command = after
                if not command and not self._stop.is_set():
                    command = record_and_transcribe(5.0, self.language)
                if command:
                    self.on_command(command)
                self.on_state('wake-idle')
            except MicrophoneUnavailable as exc:
                self.on_error(str(exc))
                break
            except Exception as exc:
                # Recognition misses are normal in continuous mode; avoid a hot error loop.
                self.on_error(str(exc))
                time.sleep(0.8)
        self.on_state('idle')
