from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceStyle:
    name: str
    speed_multiplier: float = 1.0
    pitch_hz: int = 0
    volume_percent: int = 0
    pause_after_ms: int = 0


# Keep emotion changes intentionally subtle. Edge neural voices already contain
# sentence-level prosody; large pitch/rate jumps make an otherwise neural voice
# sound synthetic. These profiles bias delivery instead of trying to "act" by
# heavily transforming the audio.
VOICE_STYLES: dict[str, VoiceStyle] = {
    'calm': VoiceStyle('calm', speed_multiplier=0.99, pitch_hz=0, volume_percent=0, pause_after_ms=0),
    'happy': VoiceStyle('happy', speed_multiplier=1.02, pitch_hz=4, volume_percent=2, pause_after_ms=0),
    'concerned': VoiceStyle('concerned', speed_multiplier=0.96, pitch_hz=-2, volume_percent=1, pause_after_ms=0),
    'urgent': VoiceStyle('urgent', speed_multiplier=1.07, pitch_hz=2, volume_percent=4, pause_after_ms=0),
    'professional': VoiceStyle('professional', speed_multiplier=1.0, pitch_hz=-1, volume_percent=1, pause_after_ms=0),
    'neutral': VoiceStyle('neutral', speed_multiplier=1.0, pitch_hz=0, volume_percent=0, pause_after_ms=0),
}

_URGENT = {
    'urgent', 'immediately', 'danger', 'warning', 'critical', 'emergency', 'alert', 'now',
    'turant', 'jaldi', 'khatra', 'savdhan', 'failed', 'failure', 'blocked',
}
_CONCERNED = {
    'sorry', 'careful', 'concern', 'concerned', 'problem', 'issue', 'unwell', 'hurt', 'sad',
    'dhyan', 'pareshan', 'galat', 'nahi hua', 'failed', 'samajh raha', 'samajh rahi',
}
_HAPPY = {
    'great', 'good news', 'success', 'successful', 'done', 'complete', 'completed', 'awesome',
    'excellent', 'congratulations', 'perfect', 'badhiya', 'mast', 'ho gaya', 'hogaya', 'nice',
    'khushi', 'ready',
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


def _pack_segments(segments: list[str], max_chars: int) -> list[str]:
    """Pack natural text segments into large utterances up to ``max_chars``."""
    chunks: list[str] = []
    buffer = ''
    for raw in segments:
        segment = raw.strip()
        if not segment:
            continue
        candidate = f'{buffer} {segment}'.strip()
        if buffer and len(candidate) > max_chars:
            chunks.append(buffer)
            buffer = segment
        else:
            buffer = candidate
    if buffer:
        chunks.append(buffer)
    return chunks


def _split_oversized(segment: str, max_chars: int) -> list[str]:
    """Split one oversized sentence at clauses, then words, without tiny pauses."""
    segment = segment.strip()
    if not segment:
        return []
    if len(segment) <= max_chars:
        return [segment]

    clauses = [part.strip() for part in re.split(r'(?<=[,;:])\s+', segment) if part.strip()]
    if len(clauses) > 1:
        packed = _pack_segments(clauses, max_chars)
        if all(len(part) <= max_chars for part in packed):
            return packed

    chunks: list[str] = []
    buffer = ''
    for word in segment.split():
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
    """Build continuous neural-TTS utterances using sentence boundaries.

    Earlier versions emitted every sentence as its own TTS process. That made
    speech audibly stop after each line while the next network synthesis/process
    started. We now pack adjacent sentences into the same utterance until the
    configured bound is reached. Punctuation remains inside the utterance, so the
    neural voice provides its own natural micro-pauses without controller-added
    silence. Only genuinely oversized sentences are split further.
    """
    spoken = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not spoken:
        return []
    max_chars = max(80, min(int(max_chars), 1200))
    sentences = [part.strip() for part in re.split(r'(?<=[.!?।])\s+', spoken) if part.strip()]
    if not sentences:
        sentences = [spoken]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_length = 0

    def flush() -> None:
        nonlocal buffer, buffer_length
        if buffer:
            chunks.append(' '.join(buffer))
            buffer = []
            buffer_length = 0

    for sentence in sentences:
        if len(sentence) > max_chars:
            flush()
            chunks.extend(_split_oversized(sentence, max_chars))
            continue

        added = len(sentence) + (1 if buffer else 0)
        if buffer and buffer_length + added > max_chars:
            flush()
        buffer.append(sentence)
        buffer_length += len(sentence) + (1 if buffer_length else 0)

    flush()
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
