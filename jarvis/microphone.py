from __future__ import annotations

import array
import math
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


def _rms_int16(data: bytes) -> float:
    if not data:
        return 0.0
    samples = array.array('h')
    samples.frombytes(data)
    if not samples:
        return 0.0
    return math.sqrt(sum(int(v) * int(v) for v in samples) / len(samples))


def _transcribe_pcm(data: bytes, sample_rate: int, language: str) -> str:
    _sd, sr = _deps()
    recognizer = sr.Recognizer()
    audio = sr.AudioData(data, sample_rate, 2)
    try:
        return recognizer.recognize_google(audio, language=language).strip()
    except sr.UnknownValueError as exc:
        raise RuntimeError('Voice clear nahi samajh aayi. Dobara thoda clearly bolo.') from exc
    except sr.RequestError as exc:
        raise RuntimeError(f'Speech recognition service unavailable: {exc}') from exc


def record_and_transcribe(
    duration: float = 6.0,
    language: str = 'en-IN',
    sample_rate: int = 16000,
) -> str:
    """Compatibility push-to-talk recorder with a fixed maximum duration."""
    sd, _sr = _deps()
    duration = max(1.0, min(float(duration), 20.0))
    frames = int(sample_rate * duration)
    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=0, dtype='int16', channels=1) as stream:
            data, _overflowed = stream.read(frames)
    except Exception as exc:
        raise MicrophoneUnavailable(f'Microphone recording failed: {exc}') from exc
    return _transcribe_pcm(bytes(data), sample_rate, language)


def record_until_silence(
    language: str = 'en-IN',
    sample_rate: int = 16000,
    max_seconds: float = 15.0,
    start_timeout: float = 5.0,
    silence_seconds: float = 0.75,
    speech_threshold: float = 420.0,
    preroll_seconds: float = 0.25,
    on_speech_start: Callable[[], None] | None = None,
) -> str:
    """VAD-style capture that stops naturally after the user finishes speaking.

    It uses local RMS energy only for endpointing; transcription remains the existing
    SpeechRecognition backend. This keeps microphone capture fast and avoids a fixed
    six-second wait for short commands.
    """
    sd, _sr = _deps()
    max_seconds = max(2.0, min(float(max_seconds), 30.0))
    start_timeout = max(1.0, min(float(start_timeout), max_seconds))
    silence_seconds = max(0.35, min(float(silence_seconds), 2.5))
    threshold = max(40.0, float(speech_threshold))
    block_ms = 30
    block_frames = int(sample_rate * block_ms / 1000)
    preroll_blocks = max(1, int(preroll_seconds * 1000 / block_ms))
    silence_blocks = max(1, int(silence_seconds * 1000 / block_ms))
    max_blocks = max(1, int(max_seconds * 1000 / block_ms))
    start_blocks = max(1, int(start_timeout * 1000 / block_ms))

    captured: list[bytes] = []
    preroll: list[bytes] = []
    speech_started = False
    quiet_count = 0

    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=block_frames,
            dtype='int16',
            channels=1,
        ) as stream:
            for index in range(max_blocks):
                chunk, _overflowed = stream.read(block_frames)
                raw = bytes(chunk)
                level = _rms_int16(raw)

                if not speech_started:
                    preroll.append(raw)
                    if len(preroll) > preroll_blocks:
                        preroll.pop(0)
                    if level >= threshold:
                        speech_started = True
                        captured.extend(preroll)
                        preroll.clear()
                        if on_speech_start:
                            try:
                                on_speech_start()
                            except Exception:
                                pass
                    elif index >= start_blocks:
                        return ''
                    continue

                captured.append(raw)
                if level < threshold:
                    quiet_count += 1
                    if quiet_count >= silence_blocks:
                        break
                else:
                    quiet_count = 0
    except Exception as exc:
        raise MicrophoneUnavailable(f'Microphone recording failed: {exc}') from exc

    if not captured:
        return ''
    return _transcribe_pcm(b''.join(captured), sample_rate, language)


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
                    command = record_until_silence(language=self.language, max_seconds=12.0)
                if command:
                    self.on_command(command)
                self.on_state('wake-idle')
            except MicrophoneUnavailable as exc:
                self.on_error(str(exc))
                break
            except Exception as exc:
                self.on_error(str(exc))
                time.sleep(0.8)
        self.on_state('idle')
