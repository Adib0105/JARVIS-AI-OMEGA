from __future__ import annotations

import os
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

from .config import settings
from .logging_utils import CRASH_DIR, LOG_DIR
from .product_paths import config_env_path
from .updater import check_latest_release, download_update, launch_update


EDITABLE_KEYS = {
    'ENABLE_VOICE_OUTPUT', 'VOICE_PROFILE', 'VOICE_EMOTION_ENABLED', 'VOICE_STREAMING_ENABLED',
    'VOICE_BARGE_IN', 'VOICE_CHUNK_CHARS',
    'EDGE_VOICE_RATE', 'EDGE_VOICE_VOLUME', 'EDGE_VOICE_PITCH',
    'VOICE_HINDI', 'VOICE_HINGLISH', 'VOICE_ENGLISH', 'VOICE_FALLBACK',
    'TTS_TIMEOUT_SECONDS', 'OFFLINE_TTS_TIMEOUT_SECONDS',
    'ENABLE_MIC_INPUT', 'ENABLE_WAKE_WORD', 'WAKE_WORD', 'SPEECH_LANGUAGE', 'MIC_RECORD_SECONDS',
    'WAKE_CHUNK_SECONDS', 'VOICE_CONTINUOUS_SECONDS',
    'REQUIRE_LOCAL_APPROVAL', 'ENABLE_DESKTOP_AUTOMATION', 'ENABLE_DOCUMENT_INTELLIGENCE',
    'ENABLE_CODING_TOOLS', 'ENABLE_GOOGLE_WORKSPACE',
    'MODEL_ROUTING', 'FAST_MODEL', 'SMART_MODEL', 'VISION_MODEL',
    'ENABLE_LOCAL_FALLBACK', 'LOCAL_AI_BASE_URL', 'LOCAL_AI_MODEL',
    'AUTO_SUMMARIZE', 'SUMMARIZE_AFTER_MESSAGES',
    'AI_TIMEOUT_SECONDS', 'VISION_TIMEOUT_SECONDS', 'MISSION_TIMEOUT_SECONDS',
    'MISSION_MAX_STEPS', 'SYSTEM_REFRESH_MS', 'REMINDER_POLL_SECONDS',
}


def _env_path() -> Path:
    return config_env_path()


def update_env_values(values: dict[str, str]) -> None:
    cleaned = {k: str(v).strip() for k, v in values.items() if k in EDITABLE_KEYS}
    if not cleaned:
        return
    from .first_run import _replace_env_values
    _replace_env_values(_env_path(), cleaned)


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri())


def show_update_dialog(root: tk.Misc) -> None:
    """Check, download, verify and launch an upgrade installer from a GitHub Release."""
    try:
        result = check_latest_release(settings.app_version)
    except Exception as exc:
        messagebox.showerror('JARVIS OMEGA Update Check', str(exc), parent=root)
        return
    message = result.get('message', 'Update check completed.')
    if not result.get('available'):
        messagebox.showinfo('JARVIS OMEGA Update Check', message, parent=root)
        return
    if not result.get('installer') or not result.get('checksum'):
        messagebox.showwarning(
            'JARVIS OMEGA Update Available',
            message + '\n\nThis release is missing the verified installer/update assets. Automatic update was refused.',
            parent=root,
        )
        return
    if not messagebox.askyesno(
        'JARVIS OMEGA Update Available',
        message + '\n\nDownload and verify this update now?',
        parent=root,
    ):
        return
    try:
        installer = download_update(result)
    except Exception as exc:
        messagebox.showerror('JARVIS OMEGA Update Download', str(exc), parent=root)
        return
    if not messagebox.askyesno(
        'JARVIS OMEGA Update Ready',
        'Update downloaded and SHA-256 verified.\n\nRestart & Update now?\n\nYour LocalAppData account, memory and settings are preserved by the installer.',
        parent=root,
    ):
        return
    try:
        launch_update(installer)
    except Exception as exc:
        messagebox.showerror('JARVIS OMEGA Update', str(exc), parent=root)
        return
    try:
        root.winfo_toplevel().after(300, root.winfo_toplevel().destroy)
    except Exception:
        pass


def show_settings_dialog(root: tk.Misc, on_saved=None) -> None:
    win = tk.Toplevel(root)
    win.title(f'JARVIS OMEGA {settings.app_version} // SETTINGS')
    win.geometry('690x820')
    win.minsize(650, 700)
    win.configure(bg='#06111a')
    win.transient(root)
    win.grab_set()

    tk.Label(win, text=f'JARVIS OMEGA {settings.app_version} SETTINGS', bg='#06111a', fg='#53e7ff', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=18, pady=(16, 2))
    tk.Label(win, text='API keys, Google OAuth JSON, and stored tokens are intentionally hidden. Saved changes apply after restart.', bg='#06111a', fg='#86a8b8', justify='left', font=('Segoe UI', 9), wraplength=640).pack(anchor='w', padx=18, pady=(0, 8))

    # Keep software update controls outside the scrollable form so Windows DPI/display
    # scaling can never hide the only update entry point.
    update_bar = tk.Frame(win, bg='#0a202e', bd=0, highlightthickness=1, highlightbackground='#12394c')
    update_bar.pack(fill='x', padx=18, pady=(0, 8))
    update_text = tk.Frame(update_bar, bg='#0a202e')
    update_text.pack(side='left', fill='x', expand=True, padx=(12, 6), pady=8)
    tk.Label(update_text, text='SOFTWARE UPDATE', bg='#0a202e', fg='#ffd166', font=('Consolas', 9, 'bold')).pack(anchor='w')
    tk.Label(update_text, text=f'Current version: {settings.app_version}', bg='#0a202e', fg='#86a8b8', font=('Segoe UI', 9)).pack(anchor='w')
    tk.Button(
        update_bar,
        text='CHECK FOR UPDATE',
        command=lambda: show_update_dialog(win),
        bg='#0b2a3a',
        fg='#53e7ff',
        activebackground='#12394c',
        activeforeground='white',
        relief='flat',
        padx=12,
        pady=7,
    ).pack(side='right', padx=10, pady=8)

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
        var = tk.BooleanVar(value=current); values[key] = var
        tk.Checkbutton(body, text=label, variable=var, bg='#091a26', fg='#dff9ff', selectcolor='#0b2a3a', activebackground='#091a26', activeforeground='white', font=('Segoe UI', 9)).pack(anchor='w', pady=1)

    def text_row(label: str, key: str, current, width: int = 31):
        row = tk.Frame(body, bg='#091a26'); row.pack(fill='x', pady=2)
        tk.Label(row, text=label, bg='#091a26', fg='#86a8b8', width=27, anchor='w').pack(side='left')
        var = tk.StringVar(value=str(current)); values[key] = var
        tk.Entry(row, textvariable=var, width=width, bg='#07131d', fg='white', insertbackground='#53e7ff', relief='flat').pack(side='right', ipady=4)

    section('VOICE + MICROPHONE')
    bool_row('Spoken replies', 'ENABLE_VOICE_OUTPUT', settings.enable_voice_output)
    text_row('Voice profile', 'VOICE_PROFILE', settings.voice_profile)
    bool_row('Emotion-aware delivery', 'VOICE_EMOTION_ENABLED', settings.voice_emotion_enabled)
    bool_row('Sentence streaming', 'VOICE_STREAMING_ENABLED', settings.voice_streaming_enabled)
    bool_row('Barge-in interruption', 'VOICE_BARGE_IN', settings.voice_barge_in)
    text_row('Voice chunk characters', 'VOICE_CHUNK_CHARS', settings.voice_chunk_chars)
    bool_row('Microphone / push-to-talk', 'ENABLE_MIC_INPUT', settings.enable_mic_input)
    bool_row('Wake-word auto start', 'ENABLE_WAKE_WORD', settings.enable_wake_word)
    text_row('Wake word', 'WAKE_WORD', settings.wake_word)
    text_row('Speech language', 'SPEECH_LANGUAGE', settings.speech_language)
    text_row('MIC seconds', 'MIC_RECORD_SECONDS', settings.mic_record_seconds)
    text_row('Wake sample seconds', 'WAKE_CHUNK_SECONDS', settings.wake_chunk_seconds)
    text_row('Continuous voice seconds', 'VOICE_CONTINUOUS_SECONDS', settings.voice_continuous_seconds)
    text_row('Voice rate', 'EDGE_VOICE_RATE', settings.edge_voice_rate)
    text_row('Voice volume', 'EDGE_VOICE_VOLUME', settings.edge_voice_volume)
    text_row('Voice pitch', 'EDGE_VOICE_PITCH', settings.edge_voice_pitch)
    text_row('English voice', 'VOICE_ENGLISH', settings.voice_english)
    text_row('Hinglish voice', 'VOICE_HINGLISH', settings.voice_hinglish)
    text_row('Hindi voice', 'VOICE_HINDI', settings.voice_hindi)
    text_row('Fallback voice', 'VOICE_FALLBACK', settings.voice_fallback)
    text_row('Edge TTS timeout', 'TTS_TIMEOUT_SECONDS', settings.tts_timeout_seconds)
    text_row('Offline TTS timeout', 'OFFLINE_TTS_TIMEOUT_SECONDS', settings.offline_tts_timeout_seconds)

    section('AGENT + COMPUTER CONTROL')
    bool_row('Require local action approvals', 'REQUIRE_LOCAL_APPROVAL', settings.require_local_approval)
    bool_row('Desktop automation tools', 'ENABLE_DESKTOP_AUTOMATION', settings.enable_desktop_automation)
    bool_row('Document intelligence', 'ENABLE_DOCUMENT_INTELLIGENCE', settings.enable_document_intelligence)
    bool_row('Coding/Git workspace tools', 'ENABLE_CODING_TOOLS', settings.enable_coding_tools)
    bool_row('Google Workspace tools', 'ENABLE_GOOGLE_WORKSPACE', settings.enable_google_workspace)
    text_row('Mission max steps', 'MISSION_MAX_STEPS', settings.mission_max_steps)
    text_row('AI request timeout', 'AI_TIMEOUT_SECONDS', settings.ai_timeout_seconds)
    text_row('Vision timeout', 'VISION_TIMEOUT_SECONDS', settings.vision_timeout_seconds)
    text_row('Mission timeout', 'MISSION_TIMEOUT_SECONDS', settings.mission_timeout_seconds)

    section('MODEL ROUTING + FALLBACK')
    text_row('Model routing', 'MODEL_ROUTING', settings.model_routing)
    text_row('Fast model (blank=primary)', 'FAST_MODEL', settings.fast_model)
    text_row('Smart model (blank=primary)', 'SMART_MODEL', settings.smart_model)
    text_row('Vision model (blank=smart)', 'VISION_MODEL', settings.vision_model)
    bool_row('Enable local AI fallback', 'ENABLE_LOCAL_FALLBACK', settings.enable_local_fallback)
    text_row('Local base URL', 'LOCAL_AI_BASE_URL', settings.local_ai_base_url)
    text_row('Local model', 'LOCAL_AI_MODEL', settings.local_ai_model)

    section('MEMORY + DASHBOARD')
    bool_row('Auto session summaries', 'AUTO_SUMMARIZE', settings.auto_summarize)
    text_row('Summarize after messages', 'SUMMARIZE_AFTER_MESSAGES', settings.summarize_after_messages)
    text_row('Telemetry refresh ms', 'SYSTEM_REFRESH_MS', settings.system_refresh_ms)
    text_row('Reminder poll seconds', 'REMINDER_POLL_SECONDS', settings.reminder_poll_seconds)

    action = tk.Frame(win, bg='#06111a'); action.place(relx=0, rely=1, relwidth=1, anchor='sw', height=64)

    def save():
        payload: dict[str, str] = {}
        for key, var in values.items():
            value = var.get(); payload[key] = ('true' if bool(value) else 'false') if isinstance(var, tk.BooleanVar) else str(value)
        try: update_env_values(payload)
        except Exception as exc:
            messagebox.showerror('Settings', str(exc), parent=win); return
        messagebox.showinfo('Settings', 'Settings saved. Restart JARVIS to apply all changes.', parent=win)
        if on_saved:
            try: on_saved()
            except Exception: pass
        win.destroy()

    tk.Button(action, text='SAVE', command=save, bg='#0b2a3a', fg='#6affb8', relief='flat', padx=12, pady=7).pack(side='left', padx=(18, 4), pady=12)
    tk.Button(action, text='CHECK UPDATE', command=lambda: show_update_dialog(win), bg='#0b2a3a', fg='#53e7ff', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
    tk.Button(action, text='OPEN LOGS', command=lambda: _open_folder(LOG_DIR), bg='#0b2a3a', fg='#ffd166', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
    tk.Button(action, text='CRASH REPORTS', command=lambda: _open_folder(CRASH_DIR), bg='#0b2a3a', fg='#ff5c73', relief='flat', padx=12, pady=7).pack(side='left', padx=4, pady=12)
