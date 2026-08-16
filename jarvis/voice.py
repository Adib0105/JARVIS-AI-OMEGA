from __future__ import annotations

import queue
import re
import threading

import pyttsx3

from .config import settings


_MARKDOWN_RE = re.compile(r"[`*_>#~\[\]{}|]+")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


def clean_for_speech(text: str) -> str:
    """Turn a formatted AI reply into speech-friendly plain text."""
    text = _CODE_BLOCK_RE.sub(" Code block omitted from speech. ", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _MARKDOWN_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class VoiceOutput:
    """Background text-to-speech output only. No microphone or speech input."""

    def __init__(self) -> None:
        self.enabled = settings.enable_voice_output
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        if self.enabled:
            self._thread = threading.Thread(target=self._worker, daemon=True, name="jarvis-tts")
            self._thread.start()

    def speak(self, text: str) -> None:
        if not self.enabled:
            return
        spoken = clean_for_speech(text)
        if spoken:
            self._queue.put(spoken)

    def stop(self) -> None:
        if self.enabled:
            self._queue.put(None)

    def _worker(self) -> None:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", settings.voice_rate)
            engine.setProperty("volume", settings.voice_volume)
        except Exception:
            self.enabled = False
            return

        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                # Voice failure must never crash the main JARVIS chat loop.
                continue
