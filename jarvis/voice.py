from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

from .config import settings
from .logging_utils import log_event
from .microphone import set_voice_interrupt_handler
from .voice_profiles import adjust_percent, adjust_pitch, detect_emotion, speech_chunks, voice_style


_MARKDOWN_RE = re.compile(r"[`*_>#~\[\]{}|]+")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_WORD_RE = re.compile(r"[A-Za-z']+")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+",
    flags=re.UNICODE,
)
_HINGLISH_HINTS = {
    'hai', 'hain', 'ho', 'haan', 'nahi', 'nahin', 'kya', 'kaise', 'kyun', 'kyu',
    'mujhe', 'mera', 'meri', 'mere', 'tum', 'tumhe', 'aap', 'aapko', 'kar', 'karo',
    'karna', 'krna', 'batao', 'btao', 'acha', 'accha', 'theek', 'thik', 'bhai',
    'wala', 'wali', 'ye', 'yeh', 'wo', 'woh', 'abhi', 'phir', 'fir', 'sab', 'ek',
    'se', 'me', 'mein', 'ko', 'ka', 'ki', 'ke', 'aur', 'lekin', 'agar', 'agr',
}
_SENTINEL = object()


@dataclass(frozen=True)
class _SpeechItem:
    text: str
    request_id: str | None = None
    emotion: str = 'auto'


def clean_for_speech(text: str) -> str:
    text = _CODE_BLOCK_RE.sub(' Code block speech me skip kiya gaya. ', str(text or ''))
    text = _LINK_RE.sub(r'\1', text)
    text = _MARKDOWN_RE.sub('', text)
    text = re.sub(r'https?://\S+', ' link ', text)
    text = _EMOJI_RE.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()


def detect_speech_mode(text: str) -> str:
    if len(_DEVANAGARI_RE.findall(str(text or ''))) >= 3:
        return 'hindi'
    words = {w.lower() for w in _WORD_RE.findall(str(text or ''))}
    return 'hinglish' if len(words & _HINGLISH_HINTS) >= 2 else 'english'


def choose_voice(text: str) -> str:
    mode = detect_speech_mode(text)
    if mode == 'hindi':
        return settings.voice_hindi
    if mode == 'hinglish':
        return settings.voice_hinglish
    return settings.voice_english


def edge_voice_candidates(text: str) -> list[str]:
    """Return the language-matched Indian voice followed by a distinct fallback."""
    voices = [choose_voice(text), settings.voice_fallback]
    return [voice for index, voice in enumerate(voices) if voice and voice not in voices[:index]]


def _parse_rate_percent(value: str) -> int:
    match = re.search(r'([+-]?\d+)', str(value or '0'))
    return int(match.group(1)) if match else 0


def edge_rate_for_speed(base_rate: str, speed: float) -> str:
    """Translate a human speed multiplier into the Edge-TTS percentage rate."""
    base = _parse_rate_percent(base_rate)
    adjusted = round(base + ((float(speed) - 1.0) * 100))
    adjusted = max(-50, min(100, adjusted))
    return f'{adjusted:+d}%'


class VoiceOutput:
    """Interruptible, emotional Indian neural TTS controller.

    The primary online path uses Edge neural voices and falls back to a second
    configured voice, then the packaged/offline pyttsx3 worker. Long answers can
    be sentence-chunked for lower first-audio latency and easier interruption.
    Emotion changes rate/pitch/volume conservatively; it does not add synthetic
    sound effects or pretend that a provider supports capabilities it does not.
    """

    MIN_SPEED = 0.6
    MAX_SPEED = 2.0
    SPEED_STEP = 0.1

    def __init__(self, on_state_change: Callable[[str], None] | None = None) -> None:
        self.enabled = settings.enable_voice_output
        self.muted = False
        self.on_state_change = on_state_change or (lambda _state: None)
        self._queue: queue.Queue[_SpeechItem | object] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False
        self._paused = False
        self._state = 'idle'
        self._speed = 1.0
        self._cancel_epoch = 0
        self._interrupt_reason: str | None = None
        self._current_text: str | None = None
        self._last_text: str | None = None
        self._current_emotion = 'calm'
        self._current_style = voice_style('calm')
        self._process: subprocess.Popen | None = None
        self._offline_engine = None
        if settings.voice_barge_in:
            set_voice_interrupt_handler(self.interrupt_for_input)
        if self.enabled:
            self._thread = threading.Thread(target=self._worker, daemon=True, name='jarvis-tts')
            self._thread.start()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def speed(self) -> float:
        with self._lock:
            return self._speed

    @property
    def speed_label(self) -> str:
        return f'{self.speed:.1f}x'

    @property
    def emotion(self) -> str:
        with self._lock:
            return self._current_emotion

    @property
    def profile_snapshot(self) -> dict[str, object]:
        style = self._active_style('')
        return {
            'profile': settings.voice_profile,
            'emotion': self.emotion,
            'voice_english': settings.voice_english,
            'voice_hindi': settings.voice_hindi,
            'voice_hinglish': settings.voice_hinglish,
            'fallback': settings.voice_fallback,
            'streaming': settings.voice_streaming_enabled,
            'barge_in': settings.voice_barge_in,
            'speed_multiplier': style.speed_multiplier,
        }

    def _emit(self, state: str) -> None:
        with self._lock:
            self._state = state
        try:
            self.on_state_change(state)
        except Exception:
            pass

    def _select_emotion(self, text: str, emotion: str | None) -> str:
        selected = str(emotion or 'auto').strip().lower()
        if not settings.voice_emotion_enabled:
            return 'neutral'
        return detect_emotion(text) if selected in {'', 'auto'} else selected

    def _active_style(self, text: str):
        style = getattr(self, '_current_style', None)
        if style is not None:
            return style
        return voice_style('neutral', text)

    def speak(
        self,
        text: str,
        *,
        request_id: str | None = None,
        emotion: str | None = 'auto',
        stream: bool | None = None,
    ) -> None:
        if not self.enabled or self.muted:
            return
        spoken = clean_for_speech(text)
        if not spoken:
            return
        selected_emotion = self._select_emotion(spoken, emotion)
        use_streaming = settings.voice_streaming_enabled if stream is None else bool(stream)
        pieces = speech_chunks(spoken, settings.voice_chunk_chars) if use_streaming else [spoken]
        with self._lock:
            if self._shutdown:
                return
            self._last_text = spoken
        for piece in pieces:
            self._queue.put(_SpeechItem(piece, request_id, selected_emotion))

    def speak_stream(
        self,
        chunks: Iterable[str],
        *,
        request_id: str | None = None,
        emotion: str | None = 'auto',
    ) -> None:
        """Accept text chunks from a streaming model without requiring full-response buffering."""
        for chunk in chunks:
            spoken = clean_for_speech(chunk)
            if spoken:
                self.speak(spoken, request_id=request_id, emotion=emotion, stream=False)

    def interrupt_for_input(self) -> None:
        """Barge-in hook: microphone/wake word can immediately yield the floor to the user."""
        with self._lock:
            active = bool(self._current_text) or self._paused or not self._queue.empty()
        if active:
            self.stop()

    def play(self) -> bool:
        with self._condition:
            if self._shutdown or not self.enabled or self.muted:
                return False
            if self._paused:
                self._paused = False
                self._interrupt_reason = None
                self._condition.notify_all()
                return True
            if self._current_text:
                return True
            last = self._last_text
        if last:
            self.speak(last)
            return True
        return False

    def pause(self) -> bool:
        with self._condition:
            if self._shutdown or self._paused or not self._current_text:
                return False
            self._paused = True
            self._interrupt_reason = 'pause'
            process = self._process
            engine = self._offline_engine
        self._terminate_process(process)
        self._stop_offline_engine(engine)
        self._emit('paused')
        return True

    def resume(self) -> bool:
        with self._condition:
            if not self._paused or self._shutdown:
                return False
            self._paused = False
            self._interrupt_reason = None
            self._condition.notify_all()
        return True

    def toggle_pause(self) -> str:
        if self.paused:
            self.resume()
            return 'playing'
        if self.pause():
            return 'paused'
        return 'playing' if self.play() else 'idle'

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def stop(self) -> None:
        with self._condition:
            self._cancel_epoch += 1
            self._paused = False
            self._interrupt_reason = 'stop'
            process = self._process
            engine = self._offline_engine
            self._condition.notify_all()
        self._drain_queue()
        self._terminate_process(process)
        self._stop_offline_engine(engine)
        self._emit('idle')

    def mute(self) -> None:
        self.muted = True
        self.stop()

    def unmute(self) -> None:
        self.muted = False

    def toggle(self) -> bool:
        if self.muted:
            self.unmute()
            return True
        self.mute()
        return False

    def _set_speed(self, value: float) -> float:
        value = round(max(self.MIN_SPEED, min(self.MAX_SPEED, float(value))), 1)
        with self._condition:
            changed = value != self._speed
            self._speed = value
            process = self._process
            engine = self._offline_engine
            should_restart = changed and bool(self._current_text) and not self._paused and not self._shutdown
            if should_restart:
                self._interrupt_reason = 'restart'
        if should_restart:
            self._terminate_process(process)
            self._stop_offline_engine(engine)
        return value

    def speed_up(self) -> float:
        return self._set_speed(self.speed + self.SPEED_STEP)

    def speed_down(self) -> float:
        return self._set_speed(self.speed - self.SPEED_STEP)

    def reset_speed(self) -> float:
        return self._set_speed(1.0)

    def test(self, mode: str = 'hinglish') -> None:
        samples = {
            'hindi': f'नमस्ते। मैं जार्विस ओमेगा {settings.app_version} हूँ। सिस्टम ऑनलाइन है और मैं आपकी मदद के लिए तैयार हूँ।',
            'english': f'Hello. JARVIS OMEGA {settings.app_version} is online. All core systems are ready.',
            'hinglish': f'JARVIS OMEGA {settings.app_version} online hai. Main ready hoon, bataiye kya karna hai.',
        }
        self.speak(samples.get(mode, samples['hinglish']), emotion='happy')

    def shutdown(self, wait: bool = True) -> None:
        with self._condition:
            if self._shutdown:
                return
            self._shutdown = True
            self._cancel_epoch += 1
            self._paused = False
            self._interrupt_reason = 'shutdown'
            process = self._process
            engine = self._offline_engine
            self._condition.notify_all()
        self._drain_queue()
        self._terminate_process(process)
        self._stop_offline_engine(engine)
        self._queue.put(_SENTINEL)
        if wait and self._thread and self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=3.0)
        if settings.voice_barge_in:
            set_voice_interrupt_handler(None)
        self._emit('idle')

    @staticmethod
    def _terminate_process(process: subprocess.Popen | None) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == 'nt':
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=False,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    process.kill()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    @staticmethod
    def _stop_offline_engine(engine) -> None:
        if engine is None:
            return
        try:
            engine.stop()
        except Exception:
            pass

    @staticmethod
    def _log_worker_failure(process: subprocess.Popen | None, event: str, **fields) -> None:
        error = ''
        stream = getattr(process, 'stderr', None)
        if stream is not None:
            try:
                error = str(stream.read() or '')[-2000:]
            except Exception:
                error = ''
        log_event('ERROR', event, failed=True, error=error or 'worker exited non-zero', **fields)

    def _edge_parameters(self, text: str) -> tuple[str, str, str]:
        style = self._active_style(text)
        rate = edge_rate_for_speed(
            settings.edge_voice_rate,
            self.speed * float(style.speed_multiplier),
        )
        volume = adjust_percent(settings.edge_voice_volume, style.volume_percent, minimum=-50, maximum=100)
        pitch = adjust_pitch(settings.edge_voice_pitch, style.pitch_hz)
        return rate, volume, pitch

    def _speak_edge_voice(self, text: str, voice: str, timeout: float) -> str:
        path = None
        process = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as handle:
                handle.write(text)
                path = handle.name
            rate, volume, pitch = self._edge_parameters(text)
            command = [
                sys.executable,
                '-m',
                'edge_playback',
                '--voice', voice,
                f'--rate={rate}',
                f'--volume={volume}',
                f'--pitch={pitch}',
                '--file', path,
            ]
            creationflags = 0
            if os.name == 'nt' and hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
            )
            with self._lock:
                self._process = process
            try:
                return_code = process.wait(timeout=max(0.1, float(timeout)))
            except subprocess.TimeoutExpired:
                self._terminate_process(process)
                log_event('ERROR', 'edge_tts_worker_timeout', failed=True, voice=voice, timeout_seconds=timeout)
                return 'failed'
            with self._lock:
                interrupted = self._interrupt_reason in {'pause', 'stop', 'shutdown', 'restart'}
            if interrupted:
                return 'interrupted'
            if return_code == 0:
                return 'completed'
            self._log_worker_failure(process, 'edge_tts_worker_failed', voice=voice, exit_code=return_code)
            return 'failed'
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
            stream = getattr(process, 'stderr', None)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _speak_edge(self, text: str) -> str:
        deadline = time.monotonic() + max(0.1, settings.tts_timeout_seconds)
        for voice in edge_voice_candidates(text):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return 'failed'
            result = self._speak_edge_voice(text, voice, remaining)
            if result != 'failed':
                return result
        return 'failed'

    def _speak_offline(self, text: str) -> str:
        path = None
        process = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as handle:
                handle.write(text)
                path = handle.name
            if bool(getattr(sys, 'frozen', False)):
                command = [sys.executable, '--offline-tts-playback']
            else:
                command = [sys.executable, '-m', 'jarvis.offline_tts_worker']
            style = self._active_style(text)
            command += [
                '--file', path,
                '--rate', str(int(max(80, min(360, settings.voice_rate * self.speed * style.speed_multiplier)))),
                '--volume', str(settings.voice_volume),
            ]
            creationflags = 0
            if os.name == 'nt' and hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
            )
            with self._lock:
                self._process = process
            try:
                return_code = process.wait(timeout=max(0.1, settings.offline_tts_timeout_seconds))
            except subprocess.TimeoutExpired:
                self._terminate_process(process)
                log_event(
                    'ERROR', 'offline_tts_worker_timeout', failed=True,
                    timeout_seconds=settings.offline_tts_timeout_seconds,
                )
                return 'failed'
            with self._lock:
                interrupted = self._interrupt_reason in {'pause', 'stop', 'shutdown', 'restart'}
            if interrupted:
                return 'interrupted'
            if return_code == 0:
                return 'completed'
            self._log_worker_failure(process, 'offline_tts_worker_failed', exit_code=return_code)
            return 'failed'
        except Exception as exc:
            log_event(
                'ERROR', 'offline_tts_controller_failed', failed=True,
                error_type=type(exc).__name__, error=str(exc),
            )
            return 'failed'
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
            stream = getattr(process, 'stderr', None)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _play_text(self, text: str) -> str:
        if settings.voice_engine == 'edge':
            try:
                result = self._speak_edge(text)
            except Exception as exc:
                log_event(
                    'ERROR', 'edge_tts_controller_failed', failed=True,
                    error_type=type(exc).__name__, error=str(exc),
                )
                result = 'failed'
            if result != 'failed':
                return result
        return self._speak_offline(text)

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            speech = item if isinstance(item, _SpeechItem) else _SpeechItem(str(item))
            text = speech.text
            request_id = speech.request_id
            selected_emotion = self._select_emotion(text, speech.emotion)
            style = voice_style(selected_emotion, text)
            with self._condition:
                if self._shutdown:
                    break
                epoch = self._cancel_epoch
                self._current_text = text
                self._current_emotion = selected_emotion
                self._current_style = style
                self._interrupt_reason = None

            while True:
                with self._condition:
                    while self._paused and epoch == self._cancel_epoch and not self._shutdown:
                        self._condition.wait(timeout=0.25)
                    if self._shutdown or epoch != self._cancel_epoch:
                        break
                    self._interrupt_reason = None

                self._emit('speaking')
                speech_started = time.perf_counter()
                log_event(
                    'INFO', 'tts_started', request_id=request_id or '', input_characters=len(text),
                    speech_mode=detect_speech_mode(text), emotion=selected_emotion,
                    voice_profile=settings.voice_profile,
                )
                result = self._play_text(text)
                log_event(
                    'INFO', 'tts_finished', request_id=request_id or '', result=result,
                    emotion=selected_emotion,
                    elapsed_ms=round((time.perf_counter() - speech_started) * 1000, 3),
                )

                with self._condition:
                    reason = self._interrupt_reason
                    cancelled = epoch != self._cancel_epoch
                    paused = self._paused
                    shutting_down = self._shutdown

                if shutting_down or cancelled or reason in {'stop', 'shutdown'}:
                    break
                if paused or reason == 'pause':
                    self._emit('paused')
                    continue
                if reason == 'restart':
                    time.sleep(0.03)
                    continue
                if result == 'failed':
                    self._emit('error')
                elif result == 'completed' and style.pause_after_ms > 0:
                    time.sleep(style.pause_after_ms / 1000.0)
                break

            with self._condition:
                if self._current_text == text:
                    self._current_text = None
                if not self._paused:
                    self._interrupt_reason = None
            if not self._shutdown and not self._paused:
                self._emit('idle')

        self._emit('idle')


__all__ = [
    'VoiceOutput', 'choose_voice', 'clean_for_speech', 'detect_speech_mode',
    'edge_rate_for_speed', 'edge_voice_candidates',
]
