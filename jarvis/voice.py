from __future__ import annotations

import os
import signal
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable

from .config import settings
from .voice_profiles import load_profile, save_profile, profile_overrides


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
        self._preference_path = settings.db_path.parent / 'voice_preferences.json'
        self.profile = load_profile(self._preference_path)
        self.on_state_change = on_state_change or (lambda _state: None)
        self._queue: queue.Queue[tuple[int, str] | object] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False
        self._paused = False
        self._state = 'idle'
        self._speed = 1.0
        self._cancel_epoch = 0
        self._interrupt_reason: str | None = None
        self._active_epoch = 0
        self.last_error: str | None = None
        self._current_text: str | None = None
        self._last_text: str | None = None
        self._process: subprocess.Popen | None = None
        if self.enabled:
            self._thread = threading.Thread(target=self._worker, daemon=True, name='jarvis-tts')
            self._thread.start()

    @property
    def engine(self) -> str:
        return profile_overrides(self.profile).get('VOICE_ENGINE', settings.voice_engine)

    def set_profile(self, name: str) -> None:
        profile_overrides(name)
        save_profile(self._preference_path, name)
        self.stop()
        with self._lock:
            self.profile = name
            self.last_error = None

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

    def speak(self, text: str) -> None:
        if not self.enabled or self.muted:
            return
        spoken = clean_for_speech(text)
        if not spoken:
            return
        with self._lock:
            if self._shutdown:
                return
            self._last_text = spoken
            self._queue.put((self._cancel_epoch, spoken))

    def play(self) -> bool:
        """Resume paused speech, or replay the last utterance after STOP."""
        with self._condition:
            if self._shutdown or not self.enabled or self.muted:
                return False
            if self._paused:
                self._paused = False
                self._condition.notify_all()
                return True
            if self._current_text and self._active_epoch == self._cancel_epoch:
                return True
            last = self._last_text
            if last:
                self._queue.put((self._cancel_epoch, last))
                return True
        return False

    def pause(self) -> bool:
        with self._condition:
            if self._shutdown or self._paused or not self._current_text:
                return False
            self._paused = True
            self._interrupt_reason = 'pause'
            process = self._process
        self._terminate_process(process)
        self._emit('paused')
        return True

    def resume(self) -> bool:
        with self._condition:
            if not self._paused or self._shutdown:
                return False
            self._paused = False
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
            self._condition.notify_all()
            self._drain_queue()
        self._terminate_process(process)
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
            should_restart = changed and bool(self._current_text) and not self._paused and not self._shutdown
            if should_restart:
                self._interrupt_reason = 'restart'
        if should_restart:
            self._terminate_process(process)
        return value

    def speed_up(self) -> float:
        return self._set_speed(self.speed + self.SPEED_STEP)

    def speed_down(self) -> float:
        return self._set_speed(self.speed - self.SPEED_STEP)

    def reset_speed(self) -> float:
        return self._set_speed(1.0)

    def test(self, mode: str = 'hinglish') -> None:
        samples = {
            'hindi': 'नमस्ते आदिब। मैं तुम्हारी एआई असिस्टेंट हूँ। बताओ, आज मैं तुम्हारी क्या मदद करूँ?',
            'english': 'Hi Adib. I am your AI assistant. It is lovely to hear from you. What shall we work on today?',
            'hinglish': 'Hi Adib, main tumhari AI assistant hoon. Batao, aaj main tumhari kya help karun?',
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
            self._condition.notify_all()
            self._drain_queue()
        self._terminate_process(process)
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
                process.wait(timeout=3)
            else:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=1.0)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=1)
            except Exception:
                pass

    def _interrupted(self) -> bool:
        return (self._shutdown or self.muted or self._active_epoch != self._cancel_epoch
                or self._interrupt_reason is not None)

    def _speak_process(self, text: str, engine: str) -> str:
        process = None
        # Parent owns all temporary files, including when the child is killed.
        with tempfile.TemporaryDirectory(prefix='jarvis-speech-') as directory:
            path = os.path.join(directory, 'speech.txt')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(text)
            command = ([sys.executable, '--jarvis-speech-worker'] if getattr(sys, 'frozen', False)
                       else [sys.executable, '-m', 'jarvis.speech_worker'])
            command += ['--engine', engine, '--speed', str(self.speed), '--profile', self.profile, '--file', path]
            try:
                # Register the child atomically with cancellation. STOP cannot miss it.
                with self._lock:
                    if self._interrupted():
                        return 'interrupted'
                    process = subprocess.Popen(
                        command, env=os.environ | profile_overrides(self.profile), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        cwd=os.path.dirname(os.path.dirname(__file__)),
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0,
                        start_new_session=os.name != 'nt',
                    )
                    self._process = process
                try:
                    return_code = process.wait(timeout=max(180, min(900, len(text) / 8)))
                except subprocess.TimeoutExpired:
                    self._terminate_process(process)
                    return 'interrupted' if self._interrupted() else 'failed'
                with self._lock:
                    if self._interrupted():
                        return 'interrupted'
                return 'completed' if return_code == 0 else 'failed'
            except Exception:
                return 'interrupted' if self._interrupted() else 'failed'
            finally:
                self._terminate_process(process)
                with self._lock:
                    if self._process is process:
                        self._process = None

    def _speak_edge(self, text: str) -> str:
        return self._speak_process(text, 'edge')

    def _speak_offline(self, text: str) -> str:
        return self._speak_process(text, 'pyttsx3')

    def _play_text(self, text: str) -> str:
        self.last_error = None
        engine = self.engine
        if engine in {'edge', 'openai'}:
            result = self._speak_process(text, engine)
            if result != 'failed':
                return result
            self.last_error = f'{engine} voice unavailable; using installed offline voice.'
            self._emit('fallback')
        with self._lock:
            if self._interrupted():
                return 'interrupted'
        result = self._speak_offline(text)
        if result == 'failed':
            self.last_error = 'Speech failed. Check audio output, voice packages and selected engine credentials.'
        return result

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            epoch, text = item
            with self._condition:
                if self._shutdown:
                    break
                if epoch != self._cancel_epoch or self.muted:
                    continue
                self._active_epoch = epoch
                self._current_text = text
                self._interrupt_reason = None

            result = 'interrupted'
            while True:
                with self._condition:
                    while self._paused and epoch == self._cancel_epoch and not self._shutdown:
                        self._condition.wait(timeout=0.25)
                    if self._shutdown or epoch != self._cancel_epoch:
                        break
                    self._interrupt_reason = None

                self._emit('speaking')
                try:
                    result = self._play_text(text)
                except Exception:
                    self.last_error = 'Speech worker failed. Check audio setup and retry playback.'
                    result = 'failed'

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
            if not self._shutdown and not self._paused and self._queue.empty():
                self._emit('idle')

        if self.state != 'idle':
            self._emit('idle')
