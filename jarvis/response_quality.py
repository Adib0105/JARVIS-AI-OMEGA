from __future__ import annotations

import os
import re
import unicodedata
from typing import Protocol

from .config import settings
from .providers.deadline import RequestCancelledError


STABLE_FREE_TEXT_MODEL = os.getenv(
    'OPENROUTER_STABLE_TEXT_MODEL',
    'openai/gpt-oss-20b:free',
).strip()

_CREATOR_PATTERNS = (
    'kisne banaya', 'kisne bnaya', 'kaun banaya', 'kaun bnaya', 'creator kaun',
    'who made you', 'who created you', 'who built you', 'your creator',
    'tumhe banaya', 'tumko banaya', 'tumhe bnaya', 'tumko bnaya',
)
_CAPABILITY_PATTERNS = (
    'kya kya kar sak', 'kya kar sak', 'what can you do', 'capabilities', 'features',
)


class _QualityRuntime(Protocol):
    provider: object
    last_model_used: str
    last_provider_used: str


def local_identity_answer(text: str) -> str | None:
    lower = ' '.join(text.lower().split())
    if not any(pattern in lower for pattern in _CREATOR_PATTERNS):
        return None
    creator = settings.creator_name or 'Adib Azam'
    assistant = settings.assistant_name or 'JARVIS OMEGA'
    wants_capabilities = any(pattern in lower for pattern in _CAPABILITY_PATTERNS)
    base = f'{creator} ne mujhe banaya hai. Main {assistant} {settings.app_version} hoon.'
    if not wants_capabilities:
        return base
    return (
        f'{base}\n\n'
        'Main ye kaam kar sakta hoon:\n'
        '• Hinglish, Hindi aur English me AI chat, reasoning, coding aur planning\n'
        '• Image upload aur permission-based Screen Vision\n'
        '• PDF, DOCX, XLSX, CSV aur text documents ko samajhna\n'
        '• Web/news research aur local knowledge/memory search\n'
        '• Todos, reminders, notes aur verified mission planning\n'
        '• Approved Windows apps, browser search, typing, hotkeys aur clicks\n'
        '• Approved coding projects inspect/edit karna aur unit tests chalana\n'
        '• Voice reply, push-to-talk aur optional “Hey Jarvis” wake-word mode\n\n'
        'Sensitive computer actions capability policy aur approval ke bina execute nahi hote.'
    )


def clean_display_text(text: str) -> str:
    if not text:
        return ''
    value = unicodedata.normalize('NFKC', str(text)).replace('\r\n', '\n').replace('\r', '\n')
    value = re.sub(r'^```[^\n]*\n?', '', value.strip())
    value = re.sub(r'\n?```$', '', value)
    value = re.sub(r'^\s{0,3}#{1,6}\s+', '', value, flags=re.MULTILINE)
    value = re.sub(r'\*\*(.*?)\*\*', r'\1', value, flags=re.DOTALL)
    value = re.sub(r'__(.*?)__', r'\1', value, flags=re.DOTALL)
    value = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'\1', value)
    value = re.sub(r'`([^`\n]+)`', r'\1', value)
    value = re.sub(r'^\s*[-*+]\s+', '• ', value, flags=re.MULTILINE)
    value = re.sub(r'</?[A-Za-z][A-Za-z0-9_-]*\s*/?>', '', value)
    value = re.sub(r'[ \t]+\n', '\n', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def looks_garbled(answer: str, user_text: str = '') -> bool:
    if not answer or len(answer.strip()) < 2 or '\ufffd' in answer:
        return True
    if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', answer) and not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', user_text):
        return True
    if len(re.findall(r'</?[A-Za-z][A-Za-z0-9_-]*\s*/?>', answer)) >= 2:
        return True
    transitions = 0
    previous = None
    for char in answer:
        if char.isspace() or char.isdigit() or unicodedata.category(char).startswith('P'):
            continue
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            script = 'devanagari'
        elif char.isascii():
            script = 'latin'
        elif 0x3040 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF:
            script = 'cjk'
        else:
            script = 'other'
        if previous and script != previous:
            transitions += 1
        previous = script
    return len(answer) < 1200 and transitions > 28


def preferred_text_model(configured_model: str, kind: str = 'chat') -> str:
    if settings.provider == 'openrouter' and configured_model == 'openrouter/free' and kind != 'image':
        return STABLE_FREE_TEXT_MODEL
    return configured_model


def repair_answer(runtime: _QualityRuntime, user_text: str, bad_answer: str) -> str:
    if settings.provider != 'openrouter':
        return bad_answer
    try:
        turn = runtime.provider.chat(
            system=(
                f'You are {settings.assistant_name} {settings.app_version}, created by {settings.creator_name}. '
                'Answer directly in clean Hinglish/English matching the user. Use only Latin and Devanagari '
                'unless another script was requested. Do not output broken HTML/template tokens.'
            ),
            messages=[{'role': 'user', 'content': user_text}],
            model=STABLE_FREE_TEXT_MODEL,
            timeout=settings.ai_timeout_seconds,
        )
        runtime.last_model_used = turn.model or STABLE_FREE_TEXT_MODEL
        runtime.last_provider_used = 'openrouter-quality-retry'
        return turn.text.strip() or bad_answer
    except RequestCancelledError:
        raise
    except Exception:
        return bad_answer


__all__ = [
    'STABLE_FREE_TEXT_MODEL',
    'clean_display_text',
    'local_identity_answer',
    'looks_garbled',
    'preferred_text_model',
    'repair_answer',
]
