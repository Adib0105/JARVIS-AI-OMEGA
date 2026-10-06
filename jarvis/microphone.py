from __future__ import annotations

from contextlib import contextmanager
import array
import math
import threading
import queue
import time
from typing import Callable

from .config import settings


class MicrophoneUnavailable(RuntimeError):
    pass


def _deps():
    try:
        import sounddevice as sd
        if settings.speech_engine == 'google':
            import speech_recognition as sr
        else:
            sr = None
    except Exception as exc:
        raise MicrophoneUnavailable(
            'Optional microphone packages are not available. Run setup_windows.ps1 again to install '
            'sounddevice and SpeechRecognition.'
        ) from exc
    return sd, sr


_CAPTURE_LOCK = threading.Lock()
_ASR_LOCK = threading.Lock()


@contextmanager
def _exclusive_stream(sd, **kwargs):
    if not _CAPTURE_LOCK.acquire(blocking=False):
        raise MicrophoneUnavailable('Microphone already in use. Stop wake-word/listening before starting another recording.')
    try:
        with sd.RawInputStream(**kwargs) as stream:
            yield stream
    finally:
        _CAPTURE_LOCK.release()



def _capture_blocks(sd, frames, sample_rate, *, stop_event=None, seconds=15):
    """One stream-owning worker; the caller can cancel even a stalled native read.

    A wedged driver retains the ownership lock until it really exits. Recovery
    never opens a competing stream or pretends that a Python timeout killed it.
    """
    pending = queue.Queue(maxsize=8)
    done = threading.Event()
    stream_ready = threading.Event()
    holder = []
    errors = []
    def produce():
        try:
            with _exclusive_stream(sd, samplerate=sample_rate, blocksize=frames,
                                   dtype='int16', channels=1, device=input_device()) as stream:
                holder.append(stream)
                stream_ready.set()
                while not done.is_set():
                    value = stream.read(frames)
                    while not done.is_set():
                        try:
                            pending.put(value, timeout=0.05)
                            break
                        except queue.Full:
                            continue
        except Exception as exc:
            errors.append(exc)
        finally:
            stream_ready.set()
    worker = threading.Thread(target=produce, daemon=True, name='jarvis-mic-owner')
    worker.start()
    deadline, last_audio = time.monotonic() + seconds + 2, time.monotonic()
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            now = time.monotonic()
            if now >= deadline or now - last_audio > 2:
                raise MicrophoneUnavailable('Microphone timed out; reconnect/select the input device.')
            try:
                chunk, overflow = pending.get(timeout=0.05)
            except queue.Empty:
                if errors:
                    raise errors[0]
                if not worker.is_alive():
                    return
                continue
            last_audio = time.monotonic()
            if overflow:
                raise MicrophoneUnavailable('Microphone overflowed; command was not executed. Please retry.')
            yield chunk
    finally:
        done.set()
        def abort():
            if holder:
                try:
                    holder[0].abort()
                except Exception:
                    pass  # caller has already cancelled; ownership is not released here
        # Some faulty native drivers can block abort too. Do not block the UI or
        # cancellation path on that call; the stream owner alone closes/releases.
        threading.Thread(target=abort, daemon=True, name='jarvis-mic-abort').start()
        worker.join(timeout=0.25)


def _bounded_transcribe(recognize, data, rate, language, stop_event):
    if stop_event is not None and stop_event.is_set():
        return ''
    if not _ASR_LOCK.acquire(blocking=False):
        raise MicrophoneUnavailable('Previous speech recognition is still stopping; retry after it exits.')
    result = queue.Queue(maxsize=1)
    def worker():
        try:
            result.put((True, recognize(data, rate, language)))
        except BaseException as exc:
            error = exc if isinstance(exc, Exception) else MicrophoneUnavailable(f'Speech worker exited: {type(exc).__name__}')
            result.put((False, error))
        finally:
            # A caller timing out/cancelling cannot kill a Python/native worker.
            # Retain ownership until actual exit, rather than spawning duplicates.
            _ASR_LOCK.release()
    try:
        threading.Thread(target=worker, daemon=True, name='jarvis-command-asr').start()
    except BaseException:
        _ASR_LOCK.release()
        raise
    deadline = time.monotonic() + 20
    while stop_event is None or not stop_event.is_set():
        if time.monotonic() >= deadline:
            raise MicrophoneUnavailable('Command transcription timed out. Please retry.')
        try:
            ok, value = result.get(timeout=0.05)
        except queue.Empty:
            continue
        if not ok:
            raise value
        return '' if stop_event is not None and stop_event.is_set() else value
    return ''

def input_device():
    value = settings.mic_device.strip()
    return int(value) if value.isdecimal() else value or None


def _rms_int16(data: bytes) -> float:
    if not data:
        return 0.0
    samples = array.array('h')
    samples.frombytes(data)
    if not samples:
        return 0.0
    return math.sqrt(sum(int(v) * int(v) for v in samples) / len(samples))


def _transcribe_pcm(data: bytes, sample_rate: int, language: str) -> str:
    if settings.speech_engine == 'vosk':
        from .offline_speech import transcribe_vosk
        return transcribe_vosk(data, sample_rate, settings.vosk_model_path)
    if settings.speech_engine != 'google':
        raise RuntimeError('SPEECH_ENGINE must be google or vosk.')
    _sd, sr = _deps()
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 15
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
    chunks = []
    with __import__('contextlib').closing(_capture_blocks(sd, int(sample_rate * .03), sample_rate, seconds=duration)) as audio:
        for chunk in audio:
            chunks.append(bytes(chunk))
            if sum(map(len, chunks)) >= int(sample_rate * duration) * 2:
                break
    return _bounded_transcribe(_transcribe_pcm, b''.join(chunks), sample_rate, language, None)


def record_until_silence(
    language: str = 'en-IN',
    sample_rate: int = 16000,
    max_seconds: float = 15.0,
    start_timeout: float = 5.0,
    silence_seconds: float = 0.75,
    speech_threshold: float = 420.0,
    preroll_seconds: float = 0.25,
    on_speech_start: Callable[[], None] | None = None,
    stop_event: threading.Event | None = None,
    transcriber: Callable[[bytes, int, str], str] | None = None,
) -> str:
    """VAD-style capture that stops naturally after the user finishes speaking.

    It uses local RMS energy only for endpointing; transcription remains the existing
    configured Google or local Vosk backend. This keeps microphone capture fast and avoids a fixed
    six-second wait for short commands.
    """
    if stop_event is not None and stop_event.is_set():
        return ''
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
        with __import__('contextlib').closing(_capture_blocks(
            sd, block_frames, sample_rate, stop_event=stop_event, seconds=max_seconds,
        )) as audio:
            for index, chunk in enumerate(audio):
                if index >= max_blocks or (stop_event is not None and stop_event.is_set()):
                    break
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

    if not captured or (stop_event is not None and stop_event.is_set()):
        return ''
    recognize = transcriber or _transcribe_pcm
    text = _bounded_transcribe(recognize, b''.join(captured), sample_rate, language, stop_event)
    return '' if stop_event is not None and stop_event.is_set() else text


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
        if self._thread and self._thread.is_alive():
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
                from .wake_service import split_wake
                after = split_wake(heard, self.wake_word)
                if after is None:
                    continue
                self.on_state('listening')
                command = after
                if not command and not self._stop.is_set():
                    command = record_until_silence(language=self.language, max_seconds=12.0, stop_event=self._stop)
                if command and not self._stop.is_set():
                    self.on_command(command)
                self.on_state('wake-idle')
            except MicrophoneUnavailable as exc:
                self.on_error(str(exc))
                break
            except Exception as exc:
                self.on_error(str(exc))
                self._stop.wait(0.8)
        self.on_state('idle')
