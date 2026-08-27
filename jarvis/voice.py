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
from typing import Callable

from .config import settings
from .logging_utils import log_event


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


def clean_for_speech(text: str) -> str:
    text = _CODE_BLOCK_RE.sub(' Code block speech me skip kiya gaya. ', text)
    text = _LINK_RE.sub(r'\1', text)
    text = _MARKDOWN_RE.sub('', text)
    text = re.sub(r'https?://\S+', ' link ', text)
    text = _EMOJI_RE.sub('', text)
    return re.sub(r'\s+', ' ', text).strip()


def detect_speech_mode(text: str) -> str:
    if len(_DEVANAGARI_RE.findall(text)) >= 3:
        return 'hindi'
    words = {w.lower() for w in _WORD_RE.findall(text)}
    return 'hinglish' if len(words & _HINGLISH_HINTS) >= 2 else 'english'


def choose_voice(text: str) -> str:
    mode = detect_speech_mode(text)
    if mode == 'hindi':
        return settings.voice_hindi
    if mode == 'hinglish':
        return settings.voice_hinglish
    return settings.voice_english


def edge_voice_candidates(text: str) -> list[str]:
    """Return the configured voice followed by one distinct reliable fallback."""
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
    """Interruptible neural TTS controller for the V7 ARC HUD.

    Media controls are runtime-only by design:
    - stop() interrupts the current speech and clears queued speech.
    - pause()/resume() pause by interrupting and replaying the current utterance
      from its beginning when resumed. This is reliable across Edge playback and
      the pyttsx3 fallback without depending on a specific audio player backend.
    - play() resumes a paused utterance or replays the last utterance after STOP.
    - speed changes restart the current utterance at the new rate.
    - shutdown() terminates current playback before the desktop window exits.
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
        self._process: subprocess.Popen | None = None
        self._offline_engine = None
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

    def _emit(self, state: str) -> None:
        with self._lock:
            self._state = state
        try:
            self.on_state_change(state)
        except Exception:
            pass

    def speak(self, text: str, *, request_id: str | None = None) -> None:
        if not self.enabled or self.muted:
            return
        spoken = clean_for_speech(text)
        if not spoken:
            return
        with self._lock:
            if self._shutdown:
                return
            self._last_text = spoken
        self._queue.put(_SpeechItem(spoken, request_id))

    def play(self) -> bool:
        """Resume paused speech, or replay the last utterance after STOP."""
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
            self._queue.put(_SpeechItem(last))
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
        """Immediate media STOP. Worker remains alive for future speech."""
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
            'hindi': 'नमस्ते आदिब। मैं जार्विस ओमेगा वर्जन सेवन हूँ। सिस्टम ऑनलाइन है।',
            'english': 'Hello Adib. JARVIS OMEGA version seven is online. All core systems are ready.',
            'hinglish': 'Adib bhai, JARVIS OMEGA version seven online hai. ARC core ready hai.',
        }
        self.speak(samples.get(mode, samples['hinglish']))

    def shutdown(self, wait: bool = True) -> None:
        """Stop audio and terminate the TTS worker; call before destroying the UI."""
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

    def _speak_edge_voice(self, text: str, voice: str, timeout: float) -> str:
        path = None
        process = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as handle:
                handle.write(text)
                path = handle.name
            command = [
                sys.executable,
                '-m',
                'edge_playback',
                '--voice', voice,
                f'--rate={edge_rate_for_speed(settings.edge_voice_rate, self.speed)}',
                f'--volume={settings.edge_voice_volume}',
                f'--pitch={settings.edge_voice_pitch}',
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
            command += [
                '--file', path,
                '--rate', str(int(max(80, min(360, settings.voice_rate * self.speed)))),
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
            with self._condition:
                if self._shutdown:
                    break
                epoch = self._cancel_epoch
                self._current_text = text
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
                log_event('INFO', 'tts_started', request_id=request_id or '', input_characters=len(text))
                result = self._play_text(text)
                log_event(
                    'INFO', 'tts_finished', request_id=request_id or '', result=result,
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
                    # Speed changed while speaking: replay current utterance at new speed.
                    time.sleep(0.03)
                    continue
                if result == 'failed':
                    self._emit('error')
                break

            with self._condition:
                if self._current_text == text:
                    self._current_text = None
                if not self._paused:
                    self._interrupt_reason = None
            if not self._shutdown and not self._paused:
                self._emit('idle')

        self._emit('idle')
