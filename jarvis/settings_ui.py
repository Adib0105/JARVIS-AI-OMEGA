from __future__ import annotations

import os
import re
import tempfile
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

from .config import ROOT, settings
from .logging_utils import CRASH_DIR, LOG_DIR
from .updater import check_latest_release


EDITABLE_KEYS = {
    'ENABLE_VOICE_OUTPUT', 'EDGE_VOICE_RATE', 'EDGE_VOICE_VOLUME', 'EDGE_VOICE_PITCH',
    'ENABLE_MIC_INPUT', 'ENABLE_WAKE_WORD', 'WAKE_WORD', 'SPEECH_LANGUAGE', 'MIC_RECORD_SECONDS',
    'REQUIRE_LOCAL_APPROVAL', 'ENABLE_DESKTOP_AUTOMATION', 'ENABLE_DOCUMENT_INTELLIGENCE',
    'ENABLE_CODING_TOOLS', 'ENABLE_GOOGLE_WORKSPACE', 'TRUSTED_LOCAL_MODE',
    'MODEL_ROUTING', 'FAST_MODEL', 'SMART_MODEL', 'VISION_MODEL',
    'ENABLE_FIVE_LAYER_INTELLIGENCE', 'ENABLE_ADAPTIVE_ML_ROUTING',
    'ADAPTIVE_ML_MIN_CONFIDENCE', 'ADAPTIVE_ML_MAX_OBSERVATIONS',
    'ENABLE_NEURAL_SEMANTIC_ROUTING', 'NEURAL_ROUTING_MIN_CONFIDENCE',
    'EMBEDDING_BASE_URL', 'EMBEDDING_MODEL',
    'ENABLE_LOCAL_FALLBACK', 'LOCAL_AI_BASE_URL', 'LOCAL_AI_MODEL',
    'AUTO_SUMMARIZE', 'SUMMARIZE_AFTER_MESSAGES',
    'MISSION_MAX_STEPS', 'SYSTEM_REFRESH_MS', 'REMINDER_POLL_SECONDS',
}


def _env_path() -> Path:
    return ROOT / '.env'


def _read_env_lines() -> list[str]:
    path = _env_path()
    if not path.exists():
        example = ROOT / '.env.example'
        if example.exists():
            path.write_text(example.read_text(encoding='utf-8'), encoding='utf-8')
        else:
            path.write_text('', encoding='utf-8')
    return path.read_text(encoding='utf-8-sig', errors='replace').splitlines()


def update_env_values(values: dict[str, str]) -> None:
    """Update only allowlisted non-secret UI settings without exposing API/OAuth secrets."""
    cleaned = {}
    for key, value in values.items():
        if key not in EDITABLE_KEYS:
            continue
        value = str(value)
        if any(char in value for char in ('\r', '\n', '\0')):
            raise ValueError('Settings must contain a single line without null characters.')
        value = value.strip()
        # Preserve literal spaces, comment markers, apostrophes and backslashes.
        if any(char.isspace() or char in "#'\"\\" for char in value):
            value = "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
        cleaned[key] = value
    if not cleaned:
        return
    lines = _read_env_lines()
    seen: set[str] = set()
    out: list[str] = []
    pattern = re.compile(r'^\s*(?:export\s+)?([A-Z0-9_]+)\s*=')
    for line in lines:
        match = pattern.match(line)
        key = match.group(1) if match else None
        if key in cleaned:
            if key not in seen:
                out.append(f'{key}={cleaned[key]}')
            seen.add(key)
        else:
            out.append(line)
    if out and out[-1].strip():
        out.append('')
    for key, value in cleaned.items():
        if key not in seen:
            out.append(f'{key}={value}')
    destination = _env_path()
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write('\n'.join(out).rstrip() + '\n')
        temp.replace(destination)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri())


def show_update_dialog(root: tk.Misc) -> None:
    from .update_ui import open_update_window
    open_update_window(root)


def show_settings_dialog(root: tk.Misc, on_saved=None) -> None:
    win = tk.Toplevel(root)
    win.title('JARVIS OMEGA // SETTINGS')
    win.geometry('690x780')
    win.minsize(600, 400)
    win.configure(bg='#06111a')
    win.transient(root)
    win.grab_set()

    tk.Label(win, text='JARVIS SETTINGS', bg='#06111a', fg='#53e7ff', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=18, pady=(16, 2))
    tk.Label(
        win,
        text='API keys, Google OAuth JSON, and stored tokens are intentionally hidden. Saved changes apply after restart.',
        bg='#06111a', fg='#86a8b8', justify='left', font=('Segoe UI', 9), wraplength=640,
    ).pack(anchor='w', padx=18, pady=(0, 10))

    canvas = tk.Canvas(win, bg='#06111a', highlightthickness=0)
    scrollbar = tk.Scrollbar(win, orient='vertical', command=canvas.yview)
    body = tk.Frame(canvas, bg='#091a26', padx=14, pady=12)
    body.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=body, anchor='nw', width=630)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='left', fill='both', expand=True, padx=(18, 0), pady=(0, 70))
    scrollbar.pack(side='right', fill='y', padx=(0, 18), pady=(0, 70))

    values: dict[str, tk.Variable] = {}

    def section(title: str):
        tk.Label(body, text=title, bg='#091a26', fg='#ffd166', font=('Consolas', 9, 'bold')).pack(anchor='w', pady=(10, 4))

    def bool_row(label: str, key: str, current: bool):
        var = tk.BooleanVar(value=current)
        values[key] = var
        tk.Checkbutton(body, text=label, variable=var, bg='#091a26', fg='#dff9ff', selectcolor='#0b2a3a', activebackground='#091a26', activeforeground='white', font=('Segoe UI', 9)).pack(anchor='w', pady=1)

    def text_row(label: str, key: str, current, width: int = 31):
        row = tk.Frame(body, bg='#091a26')
        row.pack(fill='x', pady=2)
        tk.Label(row, text=label, bg='#091a26', fg='#86a8b8', width=27, anchor='w').pack(side='left')
        var = tk.StringVar(value=str(current))
        values[key] = var
        tk.Entry(row, textvariable=var, width=width, bg='#07131d', fg='white', insertbackground='#53e7ff', relief='flat').pack(side='right', ipady=4)

    section('VOICE + MICROPHONE')
    bool_row('Spoken replies', 'ENABLE_VOICE_OUTPUT', settings.enable_voice_output)
    bool_row('Microphone / push-to-talk', 'ENABLE_MIC_INPUT', settings.enable_mic_input)
    bool_row('Wake-word auto start', 'ENABLE_WAKE_WORD', settings.enable_wake_word)
    text_row('Wake word', 'WAKE_WORD', settings.wake_word)
    text_row('Speech language', 'SPEECH_LANGUAGE', settings.speech_language)
    text_row('MIC seconds', 'MIC_RECORD_SECONDS', settings.mic_record_seconds)
    text_row('Voice rate', 'EDGE_VOICE_RATE', settings.edge_voice_rate)
    text_row('Voice volume', 'EDGE_VOICE_VOLUME', settings.edge_voice_volume)
    text_row('Voice pitch', 'EDGE_VOICE_PITCH', settings.edge_voice_pitch)

    section('AGENT + COMPUTER CONTROL')
    from .security.policy import trusted_local_mode_enabled
    bool_row('Power mode for allowlisted local actions', 'TRUSTED_LOCAL_MODE', trusted_local_mode_enabled())
    bool_row('Require local action approvals', 'REQUIRE_LOCAL_APPROVAL', settings.require_local_approval)
    bool_row('Desktop automation tools', 'ENABLE_DESKTOP_AUTOMATION', settings.enable_desktop_automation)
    bool_row('Document intelligence', 'ENABLE_DOCUMENT_INTELLIGENCE', settings.enable_document_intelligence)
    bool_row('Coding/Git workspace tools', 'ENABLE_CODING_TOOLS', settings.enable_coding_tools)
    bool_row('Google Workspace tools', 'ENABLE_GOOGLE_WORKSPACE', settings.enable_google_workspace)
    text_row('Mission max steps', 'MISSION_MAX_STEPS', settings.mission_max_steps)
    tk.Label(
        body,
        text='Power mode speeds up ordinary allowlisted actions. Password access, arbitrary shell, deletion, email sending and high-risk keyboard/window actions remain protected.',
        bg='#091a26', fg='#86a8b8', justify='left', wraplength=600, font=('Segoe UI', 8),
    ).pack(anchor='w', pady=(3, 6))

    section('MODEL ROUTING + FALLBACK')
    bool_row('Five-layer AI → ML → DL → GenAI → LLM stack', 'ENABLE_FIVE_LAYER_INTELLIGENCE', settings.enable_five_layer_intelligence)
    bool_row('Local adaptive ML routing', 'ENABLE_ADAPTIVE_ML_ROUTING', settings.enable_adaptive_ml_routing)
    text_row('Adaptive ML confidence (0.50–0.99)', 'ADAPTIVE_ML_MIN_CONFIDENCE', settings.adaptive_ml_min_confidence)
    text_row('Adaptive ML observation cap (100–50000)', 'ADAPTIVE_ML_MAX_OBSERVATIONS', settings.adaptive_ml_max_observations)
    bool_row('Optional embedding-based neural routing', 'ENABLE_NEURAL_SEMANTIC_ROUTING', settings.enable_neural_semantic_routing)
    text_row('Neural routing confidence (0.50–0.99)', 'NEURAL_ROUTING_MIN_CONFIDENCE', settings.neural_routing_min_confidence)
    text_row('Embedding base URL', 'EMBEDDING_BASE_URL', os.getenv('EMBEDDING_BASE_URL', ''))
    text_row('Embedding model', 'EMBEDDING_MODEL', os.getenv('EMBEDDING_MODEL', ''))
    text_row('Model routing', 'MODEL_ROUTING', settings.model_routing)
    text_row('Fast model (blank=primary)', 'FAST_MODEL', settings.fast_model)
    text_row('Smart model (blank=primary)', 'SMART_MODEL', settings.smart_model)
    text_row('Vision model (blank=smart)', 'VISION_MODEL', settings.vision_model)
    bool_row('Enable local AI fallback', 'ENABLE_LOCAL_FALLBACK', settings.enable_local_fallback)
    text_row('Local base URL', 'LOCAL_AI_BASE_URL', settings.local_ai_base_url)
    text_row('Local model', 'LOCAL_AI_MODEL', settings.local_ai_model)
    tk.Label(
        body,
        text='Adaptive ML stores bounded token hashes, never raw prompts. Neural routing uses EMBEDDING_* only when explicitly enabled.',
        bg='#091a26', fg='#86a8b8', justify='left', wraplength=600, font=('Segoe UI', 8),
    ).pack(anchor='w', pady=(3, 6))

    section('MEMORY + DASHBOARD')
    bool_row('Auto session summaries', 'AUTO_SUMMARIZE', settings.auto_summarize)
    text_row('Summarize after messages', 'SUMMARIZE_AFTER_MESSAGES', settings.summarize_after_messages)
    text_row('Telemetry refresh ms', 'SYSTEM_REFRESH_MS', settings.system_refresh_ms)
    text_row('Reminder poll seconds', 'REMINDER_POLL_SECONDS', settings.reminder_poll_seconds)

    action = tk.Frame(win, bg='#06111a')
    action.place(relx=0, rely=1, relwidth=1, anchor='sw', height=64)

    def save():
        payload: dict[str, str] = {}
        for key, var in values.items():
            value = var.get()
            payload[key] = ('true' if bool(value) else 'false') if isinstance(var, tk.BooleanVar) else str(value)
        try:
            update_env_values(payload)
        except Exception as exc:
            messagebox.showerror('Settings', str(exc), parent=win)
            return
        messagebox.showinfo('Settings', 'Settings saved. Restart JARVIS to apply all changes.', parent=win)
        if on_saved:
            try:
                on_saved()
            except Exception:
                pass
        win.destroy()

    tk.Button(action, text='SAVE', command=save, bg='#0b2a3a', fg='#6affb8', relief='flat', padx=12, pady=7).pack(side='left', padx=(18, 4), pady=12)
    tk.Button(action, text='CHECK UPDATE', command=lambda: show_update_dialog(win), bg='#0b2a3a', fg='#53e7ff', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
    tk.Button(action, text='OPEN LOGS', command=lambda: _open_folder(LOG_DIR), bg='#0b2a3a', fg='#ffd166', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
    tk.Button(action, text='CRASH REPORTS', command=lambda: _open_folder(CRASH_DIR), bg='#0b2a3a', fg='#ff5c73', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
