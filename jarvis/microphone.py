from __future__ import annotations

import threading
import time
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


def record_and_transcribe(
    duration: float = 6.0,
    language: str = 'auto',
    sample_rate: int = 16000,
    *,
    barge_in: bool = True,
) -> str:
    """Record mono PCM and transcribe Indian English/Hinglish/Hindi speech.

    Push-to-talk uses ``barge_in=True`` so starting a microphone request stops
    current JARVIS speech immediately. Continuous wake-word sampling opts out and
    interrupts only after the wake phrase is actually detected.
    """
    if barge_in:
        request_voice_interrupt()
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
    raise RuntimeError('Voice clear nahi samajh aayi. Dobara thoda clearly bolo.') from unknown


class WakeWordListener:
    """Explicit wake-word loop with a short opt-in conversational follow-up window."""

    def __init__(
        self,
        on_command: Callable[[str], None],
        on_state: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        wake_word: str = 'hey jarvis',
        language: str = 'auto',
        chunk_seconds: float = 3.5,
        continuous_seconds: float = 18.0,
    ) -> None:
        self.on_command = on_command
        self.on_state = on_state or (lambda _state: None)
        self.on_error = on_error or (lambda _message: None)
        self.wake_word = wake_word.strip().lower() or 'hey jarvis'
        self.language = language
        self.chunk_seconds = max(2.0, min(chunk_seconds, 8.0))
        self.continuous_seconds = max(0.0, min(float(continuous_seconds), 60.0))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._conversation_until = 0.0

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def conversation_active(self) -> bool:
        return self.continuous_seconds > 0 and time.monotonic() < self._conversation_until

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._conversation_until = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True, name='jarvis-wake-word')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._conversation_until = 0.0

    def _command_from_heard(self, heard: str) -> tuple[bool, str]:
        normalized = str(heard or '').strip()
        lower = normalized.lower()
        if self.wake_word in lower:
            after = normalized[lower.index(self.wake_word) + len(self.wake_word):].strip(' ,.!?')
            return True, after
        if self.conversation_active:
            return False, normalized
        return False, ''

    def _loop(self) -> None:
        self.on_state('wake-idle')
        while not self._stop.is_set():
            try:
                heard = record_and_transcribe(
                    self.chunk_seconds,
                    self.language,
                    barge_in=False,
                )
                woke, command = self._command_from_heard(heard)
                if not woke and not command:
                    continue

                if woke:
                    request_voice_interrupt()
                self.on_state('listening')
                if woke and not command and not self._stop.is_set():
                    command = record_and_transcribe(5.0, self.language, barge_in=False)
                if command:
                    self.on_command(command)
                    if self.continuous_seconds > 0:
                        self._conversation_until = time.monotonic() + self.continuous_seconds
                        self.on_state('conversation')
                    else:
                        self.on_state('wake-idle')
            except MicrophoneUnavailable as exc:
                self.on_error(str(exc))
                break
            except Exception as exc:
                # Recognition misses are normal in continuous mode; avoid a hot error loop.
                self.on_error(str(exc))
                time.sleep(0.8)
                self.on_state('conversation' if self.conversation_active else 'wake-idle')
        self.on_state('idle')


__all__ = [
    'MicrophoneUnavailable', 'WakeWordListener', 'recognition_languages',
    'record_and_transcribe', 'request_voice_interrupt', 'set_voice_interrupt_handler',
]
