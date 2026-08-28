from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceStyle:
    name: str
    speed_multiplier: float = 1.0
    pitch_hz: int = 0
    volume_percent: int = 0
    pause_after_ms: int = 90


VOICE_STYLES: dict[str, VoiceStyle] = {
    'calm': VoiceStyle('calm', speed_multiplier=0.96, pitch_hz=0, volume_percent=0, pause_after_ms=125),
    'happy': VoiceStyle('happy', speed_multiplier=1.06, pitch_hz=16, volume_percent=3, pause_after_ms=80),
    'concerned': VoiceStyle('concerned', speed_multiplier=0.91, pitch_hz=-6, volume_percent=2, pause_after_ms=145),
    'urgent': VoiceStyle('urgent', speed_multiplier=1.14, pitch_hz=8, volume_percent=6, pause_after_ms=45),
    'professional': VoiceStyle('professional', speed_multiplier=1.0, pitch_hz=-2, volume_percent=1, pause_after_ms=90),
    'neutral': VoiceStyle('neutral', speed_multiplier=1.0, pitch_hz=0, volume_percent=0, pause_after_ms=90),
}

_URGENT = {
    'urgent', 'immediately', 'danger', 'warning', 'critical', 'emergency', 'alert', 'now',
    'turant', 'jaldi', 'khatra', 'savdhan', 'failed', 'failure', 'blocked',
}
_CONCERNED = {
    'sorry', 'careful', 'concern', 'concerned', 'problem', 'issue', 'unwell', 'hurt', 'sad',
    'dhyan', 'pareshan', 'galat', 'nahi hua', 'failed',
}
_HAPPY = {
    'great', 'good news', 'success', 'successful', 'done', 'complete', 'completed', 'awesome',
    'excellent', 'congratulations', 'perfect', 'badhiya', 'mast', 'ho gaya', 'hogaya',
}
_PROFESSIONAL = {
    'report', 'analysis', 'summary', 'status', 'result', 'schedule', 'meeting', 'project',
    'deployment', 'release', 'test', 'review', 'update', 'completed',
}


def detect_emotion(text: str) -> str:
    lowered = re.sub(r'\s+', ' ', str(text or '').lower()).strip()
    if not lowered:
        return 'neutral'
    words = set(re.findall(r"[a-zA-Z']+", lowered))
    if '!' in lowered and len(lowered) < 180:
        return 'urgent' if words & _URGENT else 'happy'
    if any(phrase in lowered for phrase in _URGENT) or words & _URGENT:
        return 'urgent'
    if any(phrase in lowered for phrase in _CONCERNED) or words & _CONCERNED:
        return 'concerned'
    if any(phrase in lowered for phrase in _HAPPY) or words & _HAPPY:
        return 'happy'
    if any(phrase in lowered for phrase in _PROFESSIONAL) or words & _PROFESSIONAL:
        return 'professional'
    return 'calm'


def voice_style(emotion: str | None, text: str = '') -> VoiceStyle:
    selected = str(emotion or 'auto').strip().lower()
    if selected in {'', 'auto'}:
        selected = detect_emotion(text)
    return VOICE_STYLES.get(selected, VOICE_STYLES['neutral'])


def _split_oversized(segment: str, max_chars: int) -> list[str]:
    """Split one oversized sentence at clauses, then words, without losing text."""
    segment = segment.strip()
    if not segment:
        return []
    if len(segment) <= max_chars:
        return [segment]

    clauses = [part.strip() for part in re.split(r'(?<=[,;:])\s+', segment) if part.strip()]
    if len(clauses) == 1:
        clauses = [segment]

    chunks: list[str] = []
    for clause in clauses:
        if len(clause) <= max_chars:
            chunks.append(clause)
            continue
        buffer = ''
        for word in clause.split():
            candidate = f'{buffer} {word}'.strip()
            if buffer and len(candidate) > max_chars:
                chunks.append(buffer)
                buffer = word
            else:
                buffer = candidate
        if buffer:
            chunks.append(buffer)
    return chunks


def speech_chunks(text: str, max_chars: int = 260) -> list[str]:
    """Split speech at sentence boundaries for low latency and reliable barge-in.

    A sentence is a natural interruption boundary even when the whole answer is
    shorter than ``max_chars``. Only an oversized sentence is split further at
    clauses/words. This avoids re-buffering several complete sentences into one
    long TTS request while still keeping individual requests bounded.
    """
    spoken = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not spoken:
        return []
    max_chars = max(40, min(int(max_chars), 600))
    sentences = [part.strip() for part in re.split(r'(?<=[.!?।])\s+', spoken) if part.strip()]
    if not sentences:
        sentences = [spoken]

    chunks: list[str] = []
    for sentence in sentences:
        chunks.extend(_split_oversized(sentence, max_chars))
    return chunks


def adjust_percent(base: str, delta: int, minimum: int = -50, maximum: int = 100) -> str:
    match = re.search(r'([+-]?\d+)', str(base or '0'))
    value = int(match.group(1)) if match else 0
    value = max(minimum, min(maximum, value + int(delta)))
    return f'{value:+d}%'


def adjust_pitch(base: str, delta_hz: int) -> str:
    match = re.search(r'([+-]?\d+)', str(base or '0'))
    value = int(match.group(1)) if match else 0
    value = max(-100, min(100, value + int(delta_hz)))
    return f'{value:+d}Hz'


__all__ = [
    'VOICE_STYLES', 'VoiceStyle', 'adjust_percent', 'adjust_pitch', 'detect_emotion',
    'speech_chunks', 'voice_style',
]
