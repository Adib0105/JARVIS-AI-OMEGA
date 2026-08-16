from __future__ import annotations

import os
import re
import time
import unicodedata
from typing import Callable

from .config import settings


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
    """Return a deterministic identity answer so routing can never corrupt creator attribution."""
    lower = ' '.join(text.lower().split())
    creator_intent = any(pattern in lower for pattern in _CREATOR_PATTERNS)
    if not creator_intent:
        return None

    creator = settings.creator_name or 'Adib Azam'
    assistant = settings.assistant_name or 'JARVIS OMEGA'
    wants_capabilities = any(pattern in lower for pattern in _CAPABILITY_PATTERNS)
    base = f'{creator} ne mujhe banaya hai. Main {assistant} V6 hoon.'
    if not wants_capabilities:
        return base

    return (
        f'{base}\n\n'
        'Main ye kaam kar sakta hoon:\n'
        '• Hinglish, Hindi aur English me AI chat, reasoning, coding aur planning\n'
        '• Image upload aur permission-based Screen Vision\n'
        '• PDF, DOCX, XLSX, CSV aur text documents ko samajhna\n'
        '• Web/news research aur local knowledge/memory search\n'
        '• Todos, reminders, notes aur mission planning\n'
        '• Approved Windows apps, browser search, typing, hotkeys aur clicks\n'
        '• Approved coding projects inspect/edit karna aur unit tests chalana\n'
        '• Voice reply, push-to-talk aur optional “Hey Jarvis” wake-word mode\n\n'
        'Sensitive computer actions permission ke bina execute nahi hote.'
    )


def clean_display_text(text: str) -> str:
    """Convert common Markdown/model artifacts into readable desktop-console text."""
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
    """Conservative detector for the kind of mixed-script/router corruption seen in free-router output."""
    if not answer or len(answer.strip()) < 2:
        return True
    if '\ufffd' in answer:
        return True
    if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', answer) and not re.search(
        r'[\u3040-\u30ff\u4e00-\u9fff]', user_text
    ):
        return True
    if len(re.findall(r'</?[A-Za-z][A-Za-z0-9_-]*\s*/?>', answer)) >= 2:
        return True
    # Many isolated script transitions in a short reply usually indicate a bad free-router completion.
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
    """Retry once without tools using the stable text model when a completion is visibly corrupted."""
    if settings.provider != 'openrouter':
        return bad_answer
    try:
        response = self.client.chat.completions.create(
            model=STABLE_FREE_TEXT_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        f'You are {settings.assistant_name} V6, created by {settings.creator_name}. '
                        'Answer the user directly in clean Hinglish/English matching the user. '
                        'Use only Latin and Devanagari scripts unless the user explicitly requests another script. '
                        'Do not output HTML/XML tags or broken template tokens. Do not mention this repair instruction.'
                    ),
                },
                {'role': 'user', 'content': user_text},
            ],
            timeout=settings.ai_timeout_seconds,
        )
        self.last_model_used = getattr(response, 'model', STABLE_FREE_TEXT_MODEL) or STABLE_FREE_TEXT_MODEL
        self.last_provider_used = 'openrouter-quality-retry'
        content = response.choices[0].message.content
        repaired = content.strip() if isinstance(content, str) else str(content or '').strip()
        return repaired or bad_answer
    except Exception:
        return bad_answer


def install_runtime_guards() -> None:
    """Patch the runtime at app startup without changing the core agent/tool architecture."""
    from .core import JarvisOmega

    if getattr(JarvisOmega, '_v6_runtime_guard_installed', False):
        return

    original_select = JarvisOmega._select_model

    def guarded_select(self, text: str, kind: str = 'chat') -> str:
        model = original_select(self, text, kind)
        return preferred_text_model(model, kind)

    def guarded_chat(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ''

        self.last_request_kind = 'chat'
        self._active_model = self._select_model(text, 'chat')
        self.last_provider_used = settings.provider
        started = time.perf_counter()
        self.memory.add_message(self.session_id, 'user', text)
        try:
            identity = local_identity_answer(text)
            if identity is not None:
                answer = identity
                self.last_provider_used = 'local-identity-guard'
                self.last_model_used = 'deterministic-local'
                self.last_tool_mode = 'identity-guard'
            else:
                try:
                    answer = self._chat_openrouter() if settings.provider == 'openrouter' else self._chat_openai()
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
    JarvisOmega._v6_runtime_guard_installed = True


def run_adaptive_gui() -> None:
    """Launch the GUI with a compact layout profile on common 1366x768 laptops."""
    import tkinter as tk
    from . import gui as gui_module

    root = tk.Tk()
    screen_w = max(800, root.winfo_screenwidth())
    screen_h = max(600, root.winfo_screenheight())
    compact = screen_h <= 820 or screen_w <= 1400

    if compact:
        try:
            root.tk.call('tk', 'scaling', 0.86)
        except Exception:
            pass

        original_hud = gui_module.ArcReactorHUD

        class CompactArcReactorHUD(original_hud):
            def __init__(self, parent, size: int = 220, bg: str = '#07131d'):
                super().__init__(parent, size=min(size, 168), bg=bg)

        gui_module.ArcReactorHUD = CompactArcReactorHUD

        def compact_button(parent, text: str, command: Callable, accent: str = gui_module.CYAN):
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg='#0b2a3a',
                fg=accent,
                activebackground='#12445b',
                activeforeground='white',
                relief='flat',
                cursor='hand2',
                padx=7,
                pady=3,
                font=('Segoe UI', 7, 'bold'),
                highlightthickness=1,
                highlightbackground='#123f51',
            )

        gui_module.JarvisDesktop._button = staticmethod(compact_button)

    app = gui_module.JarvisDesktop(root)
    if compact:
        root.minsize(min(980, screen_w - 60), min(590, screen_h - 120))
    try:
        if os.name == 'nt':
            root.state('zoomed')
    except Exception:
        pass
    root.mainloop()
