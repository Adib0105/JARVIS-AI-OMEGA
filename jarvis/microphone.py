from __future__ import annotations

import threading
import time
from array import array
from typing import Callable


class MicrophoneUnavailable(RuntimeError):
    pass


_voice_interrupt_handler: Callable[[], None] | None = None
_handler_lock = threading.RLock()


def set_voice_interrupt_handler(handler: Callable[[], None] | None) -> None:
    """Register the active TTS interruption hook used by push-to-talk/wake word."""
    global _voice_interrupt_handler
    with _handler_lock:
        _voice_interrupt_handler = handler


def request_voice_interrupt() -> bool:
    with _handler_lock:
        handler = _voice_interrupt_handler
    if handler is None:
        return False
    try:
        handler()
        return True
    except Exception:
        return False


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


def recognition_languages(language: str) -> tuple[str, ...]:
    selected = str(language or 'auto').strip()
    if selected.lower() == 'auto':
        # en-IN works well for Indian English and Roman-Hindi/Hinglish; hi-IN is
        # the second pass for predominantly Hindi speech.
        return ('en-IN', 'hi-IN')
    return (selected,)


def _pcm_rms(data: bytes) -> float:
    """Return RMS energy for little-endian signed 16-bit mono PCM without NumPy."""
    raw = bytes(data or b'')
    if len(raw) < 2:
        return 0.0
    if len(raw) % 2:
        raw = raw[:-1]
    samples = array('h')
    samples.frombytes(raw)
    if not samples:
        return 0.0
    total = sum(int(sample) * int(sample) for sample in samples)
    return (total / len(samples)) ** 0.5


def _record_until_silence(stream, max_duration: float, sample_rate: int) -> tuple[bytes, bool, float]:
    """Capture speech with a bounded max duration and stop after natural trailing silence.

    The old implementation always blocked for the full configured duration even
    when the user finished speaking early. This keeps a small pre-roll, adapts to
    quiet ambient noise, and ends after about one second of trailing silence.
    """
    chunk_seconds = 0.20
    chunk_frames = max(320, int(sample_rate * chunk_seconds))
    max_chunks = max(1, int(max_duration / chunk_seconds + 0.999))
    end_silence_seconds = 1.0
    minimum_capture_seconds = 0.65

    chunks: list[bytes] = []
    ambient: list[float] = []
    speech_seen = False
    trailing_silence = 0.0
    peak_rms = 0.0
    threshold = 150.0

    for index in range(max_chunks):
        data, _overflowed = stream.read(chunk_frames)
        raw = bytes(data)
        chunks.append(raw)
        rms = _pcm_rms(raw)
        peak_rms = max(peak_rms, rms)

        # Learn only genuinely quiet pre-speech chunks. If the user starts talking
        # immediately we intentionally keep the conservative base threshold.
        if not speech_seen and rms < 450.0 and len(ambient) < 5:
            ambient.append(rms)
            noise = sum(ambient) / len(ambient)
            threshold = max(120.0, min(520.0, noise * 2.2 + 70.0))

        if rms >= threshold:
            speech_seen = True
            trailing_silence = 0.0
        elif speech_seen:
            trailing_silence += chunk_seconds

        elapsed = (index + 1) * chunk_seconds
        if speech_seen and elapsed >= minimum_capture_seconds and trailing_silence >= end_silence_seconds:
            break

    return b''.join(chunks), speech_seen, peak_rms


def record_and_transcribe(
    duration: float = 6.0,
    language: str = 'auto',
    sample_rate: int = 16000,
    *,
    barge_in: bool = True,
) -> str:
    """Record mono PCM and transcribe Indian English/Hinglish/Hindi speech.

    Push-to-talk uses ``barge_in=True`` so starting a microphone request stops
    current JARVIS speech immediately. Capture is silence-aware: it can finish
    before the maximum recording window once the user has stopped speaking.
    Continuous wake-word sampling opts out of barge-in and interrupts only after
    the wake phrase is actually detected.
    """
    if barge_in:
        request_voice_interrupt()
    sd, sr = _deps()
    duration = max(1.0, min(float(duration), 20.0))

    try:
        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=0,
            dtype='int16',
            channels=1,
        ) as stream:
            data, speech_seen, peak_rms = _record_until_silence(stream, duration, sample_rate)
    except Exception as exc:
        raise MicrophoneUnavailable(f'Microphone recording failed: {exc}') from exc

    if not data or peak_rms < 35.0:
        raise RuntimeError('Microphone me clear voice signal nahi mila. Mic level/input device check karke dobara bolo.')

    recognizer = sr.Recognizer()
    audio = sr.AudioData(data, sample_rate, 2)
    unknown = None
    for selected_language in recognition_languages(language):
        try:
            heard = recognizer.recognize_google(audio, language=selected_language).strip()
            if heard:
                return heard
        except sr.UnknownValueError as exc:
            unknown = exc
            continue
        except sr.RequestError as exc:
            raise RuntimeError(f'Speech recognition service unavailable: {exc}') from exc

    if not speech_seen:
        raise RuntimeError('Voice signal bahut low/noisy thi. Mic ke paas normal awaaz me dobara bolo.') from unknown
    raise RuntimeError('Voice clear nahi samajh aayi. Dobara normal speed me clearly bolo.') from unknown


class WakeWordListener:
    """Explicit wake-word loop with a short opt-in conversational follow-up window.

    Every listener generation owns a distinct stop event. A fast stop/start can
    therefore never clear the previous worker's stop signal and accidentally
    resurrect two concurrent wake loops. Shutdown also performs a bounded best-
    effort join without pretending a blocking external speech request is cancellable.
    """

    def __init__(
        self,
        on_command: Callable[[str], None],
        on_state: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        wake_word: str = 'hey jarvis',
        language: str = 'auto',
        chunk_seconds: float | None = None,
        continuous_seconds: float | None = None,
    ) -> None:
        from .config import settings

        configured_chunk = settings.wake_chunk_seconds if chunk_seconds is None else chunk_seconds
        configured_continuous = (
            settings.voice_continuous_seconds if continuous_seconds is None else continuous_seconds
        )
        self.on_command = on_command
        self.on_state = on_state or (lambda _state: None)
        self.on_error = on_error or (lambda _message: None)
        self.wake_word = wake_word.strip().lower() or 'hey jarvis'
        self.language = language
        self.chunk_seconds = max(2.0, min(float(configured_chunk), 8.0))
        self.continuous_seconds = max(0.0, min(float(configured_continuous), 60.0))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.RLock()
        self._conversation_until = 0.0

    @property
    def running(self) -> bool:
        with self._thread_lock:
            thread = self._thread
            stop_event = self._stop
        return bool(thread and thread.is_alive() and not stop_event.is_set())

    @property
    def conversation_active(self) -> bool:
        return self.continuous_seconds > 0 and time.monotonic() < self._conversation_until

    def start(self) -> None:
        if self.running:
            return
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._loop,
            args=(stop_event,),
            daemon=True,
            name='jarvis-wake-word',
        )
        with self._thread_lock:
            self._stop = stop_event
            self._thread = thread
            self._conversation_until = 0.0
        thread.start()

    def stop(self, *, wait: bool = True, timeout: float = 0.75) -> bool:
        with self._thread_lock:
            stop_event = self._stop
            thread = self._thread
            stop_event.set()
            self._conversation_until = 0.0
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and threading.current_thread() is not thread
        ):
            thread.join(timeout=max(0.0, min(float(timeout), 3.0)))
        return not bool(thread and thread.is_alive())

    def _command_from_heard(self, heard: str) -> tuple[bool, str]:
        normalized = str(heard or '').strip()
        lower = normalized.lower()
        if self.wake_word in lower:
            after = normalized[lower.index(self.wake_word) + len(self.wake_word):].strip(' ,.!?')
            return True, after
        if self.conversation_active:
            return False, normalized
        return False, ''

    def _loop(self, stop_event: threading.Event) -> None:
        self.on_state('wake-idle')
        while not stop_event.is_set():
            try:
                heard = record_and_transcribe(
                    self.chunk_seconds,
                    self.language,
                    barge_in=False,
                )
                if stop_event.is_set():
                    break
                woke, command = self._command_from_heard(heard)
                if not woke and not command:
                    continue

                if woke:
                    request_voice_interrupt()
                self.on_state('listening')
                if woke and not command and not stop_event.is_set():
                    command = record_and_transcribe(5.0, self.language, barge_in=False)
                if stop_event.is_set():
                    break
                if command:
                    self.on_command(command)
                    if self.continuous_seconds > 0:
                        self._conversation_until = time.monotonic() + self.continuous_seconds
                        self.on_state('conversation')
                    else:
                        self.on_state('wake-idle')
            except MicrophoneUnavailable as exc:
                if not stop_event.is_set():
                    self.on_error(str(exc))
                break
            except Exception as exc:
                if stop_event.is_set():
                    break
                self.on_error(str(exc))
                stop_event.wait(0.8)
                if not stop_event.is_set():
                    self.on_state('conversation' if self.conversation_active else 'wake-idle')
        with self._thread_lock:
            is_current = self._stop is stop_event
        if is_current:
            self.on_state('idle')


__all__ = [
    'MicrophoneUnavailable', 'WakeWordListener', 'recognition_languages',
    'record_and_transcribe', 'request_voice_interrupt', 'set_voice_interrupt_handler',
]
