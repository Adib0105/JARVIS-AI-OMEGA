from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from typing import Callable

from .config import settings
from .fast_commands import execute_fast_command


STABLE_FREE_TEXT_MODEL = os.getenv(
    'OPENROUTER_STABLE_TEXT_MODEL',
    'nvidia/nemotron-3-ultra-550b-a55b:free',
).strip()

_CREATOR_PATTERNS = (
    'kisne banaya', 'kisne bnaya', 'kaun banaya', 'kaun bnaya', 'creator kaun',
    'who made you', 'who created you', 'who built you', 'your creator',
    'tumhe banaya', 'tumko banaya', 'tumhe bnaya', 'tumko bnaya',
)
_CAPABILITY_PATTERNS = (
    'kya kya kar sak', 'kya kar sak', 'what can you do', 'capabilities', 'features',
)


def local_identity_answer(text: str) -> str | None:
    lower = ' '.join(text.lower().split())
    if not any(pattern in lower for pattern in _CREATOR_PATTERNS):
        return None
    creator = settings.creator_name or 'Adib Azam'
    assistant = settings.assistant_name or 'JARVIS OMEGA'
    wants_capabilities = any(pattern in lower for pattern in _CAPABILITY_PATTERNS)
    base = f'{creator} ne mujhe banaya hai. Main {assistant} V7 hoon.'
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


def _repair_answer(self, user_text: str, bad_answer: str) -> str:
    if settings.provider != 'openrouter':
        return bad_answer
    try:
        turn = self.provider.chat(
            system=(
                f'You are {settings.assistant_name} V7, created by {settings.creator_name}. '
                'Answer directly in clean Hinglish/English matching the user. Use only Latin and Devanagari '
                'unless another script was requested. Do not output broken HTML/template tokens.'
            ),
            messages=[{'role': 'user', 'content': user_text}],
            model=STABLE_FREE_TEXT_MODEL,
            timeout=settings.ai_timeout_seconds,
        )
        self.last_model_used = turn.model or STABLE_FREE_TEXT_MODEL
        self.last_provider_used = 'openrouter-quality-retry'
        return turn.text.strip() or bad_answer
    except Exception:
        return bad_answer


def install_runtime_guards() -> None:
    """Quality compatibility layer around the provider-neutral V7.5 router."""
    from .core import JarvisOmega
    if getattr(JarvisOmega, '_v7_runtime_guard_installed', False):
        return
    original_select = JarvisOmega._select_model

    def guarded_select(self, text: str, kind: str = 'chat') -> str:
        return preferred_text_model(original_select(self, text, kind), kind)

    def guarded_chat(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ''
        self.last_request_kind = 'chat'
        started = time.perf_counter()
        self.memory.add_message(self.session_id, 'user', text)
        try:
            # Deterministic low-risk commands execute locally first. This removes the
            # network/model round trip for commands such as "Chrome kholo" while the
            # normal permission/capability gate still remains authoritative.
            fast_answer = execute_fast_command(self, text)
            if fast_answer is not None:
                answer = fast_answer
                self.last_provider_used = 'local-fast-command'
                self.last_model_used = 'deterministic-local'
                self.last_tool_mode = 'fast-command'
            else:
                self._active_model = self._select_model(text, 'chat')
                self.last_provider_used = settings.provider
                identity = local_identity_answer(text)
                if identity is not None:
                    answer = identity
                    self.last_provider_used = 'local-identity-guard'
                    self.last_model_used = 'deterministic-local'
                    self.last_tool_mode = 'identity-guard'
                else:
                    try:
                        answer = self._chat_provider()
                    except Exception as exc:
                        answer = self._chat_local_fallback(exc)
                    if looks_garbled(answer, text):
                        answer = _repair_answer(self, text, answer)
                    answer = clean_display_text(answer)
            self.memory.add_message(self.session_id, 'assistant', answer)
            self._maybe_auto_summary()
            return answer
        finally:
            self.last_latency = time.perf_counter() - started

    JarvisOmega._select_model = guarded_select
    JarvisOmega.chat = guarded_chat
    JarvisOmega._v7_runtime_guard_installed = True


def _rebrand_widget_tree(widget) -> None:
    try:
        text = widget.cget('text')
        if isinstance(text, str) and 'V6' in text:
            widget.configure(text=text.replace('V6', 'V7'))
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _rebrand_widget_tree(child)
    except Exception:
        pass


def _rebrand_chat_history(app) -> None:
    chat = getattr(app, 'chat', None)
    if chat is None:
        return
    try:
        previous_state = str(chat.cget('state'))
        chat.configure(state='normal')
        start = '1.0'
        while True:
            index = chat.search('V6', start, stopindex='end')
            if not index:
                break
            chat.delete(index, f'{index}+2c')
            chat.insert(index, 'V7')
            start = f'{index}+2c'
        chat.configure(state=previous_state)
    except Exception:
        pass

# Remaining GUI/security compatibility hooks are intentionally kept in their existing modules.
# run_adaptive_gui is imported by desktop_app.py from this module in the full repository.


def run_adaptive_gui() -> None:
    from .gui import run_gui
    run_gui()
