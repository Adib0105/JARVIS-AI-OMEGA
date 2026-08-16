from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import tempfile
import threading

import pyttsx3

from .config import settings


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


def clean_for_speech(text: str) -> str:
    """Turn formatted AI output into compact speech-friendly text."""
    text = _CODE_BLOCK_RE.sub(" Code block speech me skip kiya gaya. ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _MARKDOWN_RE.sub("", text)
    text = re.sub(r"https?://\S+", " link ", text)
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_speech_mode(text: str) -> str:
    """Return hindi, hinglish, or english for voice selection."""
    devanagari_count = len(_DEVANAGARI_RE.findall(text))
    if devanagari_count >= 3:
        return 'hindi'

    words = {w.lower() for w in _WORD_RE.findall(text)}
    hint_count = len(words & _HINGLISH_HINTS)
    if hint_count >= 2:
        return 'hinglish'
    return 'english'


def choose_voice(text: str) -> str:
    mode = detect_speech_mode(text)
    if mode == 'hindi':
        return settings.voice_hindi
    if mode == 'hinglish':
        return settings.voice_hinglish
    return settings.voice_english


class VoiceOutput:
    """Typed-input, spoken-output TTS. No microphone or speech recognition."""

    def __init__(self) -> None:
        self.enabled = settings.enable_voice_output
        self.muted = False
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        if self.enabled:
            self._thread = threading.Thread(target=self._worker, daemon=True, name='jarvis-tts')
            self._thread.start()

    def speak(self, text: str) -> None:
        if not self.enabled or self.muted:
            return
        spoken = clean_for_speech(text)
        if spoken:
            self._queue.put(spoken)

    def mute(self) -> None:
        self.muted = True

    def unmute(self) -> None:
        self.muted = False

    def toggle(self) -> bool:
        self.muted = not self.muted
        return not self.muted

    def test(self, mode: str = 'hinglish') -> None:
        samples = {
            'hindi': 'नमस्ते आदिब। मैं जार्विस ओमेगा हूँ। मेरी आवाज़ अब थोड़ी गहरी और साफ़ है।',
            'english': 'Hello Adib. I am JARVIS OMEGA. My voice is now deeper and clearer.',
            'hinglish': 'Adib bhai, main JARVIS OMEGA hoon. Ab meri voice thodi deep, clear aur natural hai.',
        }
        self.speak(samples.get(mode, samples['hinglish']))

    def stop(self) -> None:
        if self.enabled:
            self._queue.put(None)

    def _speak_edge(self, text: str) -> None:
        voice = choose_voice(text)
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.txt', delete=False
            ) as handle:
                handle.write(text)
                path = handle.name

            command = [
                sys.executable,
                '-m',
                'edge_playback',
                '--voice',
                voice,
                f'--rate={settings.edge_voice_rate}',
                f'--volume={settings.edge_voice_volume}',
                f'--pitch={settings.edge_voice_pitch}',
                '--file',
                path,
            ]
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
            )
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    @staticmethod
    def _build_offline_engine():
        engine = pyttsx3.init()
        engine.setProperty('rate', settings.voice_rate)
        engine.setProperty('volume', settings.voice_volume)
        return engine

    def _worker(self) -> None:
        offline_engine = None

        while True:
            text = self._queue.get()
            if text is None:
                break

            if settings.voice_engine == 'edge':
                try:
                    self._speak_edge(text)
                    continue
                except Exception:
                    # Network/voice failure falls back to Windows offline TTS.
                    pass

            try:
                if offline_engine is None:
                    offline_engine = self._build_offline_engine()
                offline_engine.say(text)
                offline_engine.runAndWait()
            except Exception:
                # TTS failure must never crash the JARVIS chat loop.
                continue
