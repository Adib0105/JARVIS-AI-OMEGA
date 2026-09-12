"""Voice preferences dialog shared by the desktop extension."""
from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .voice_profiles import PROFILES
from .voice_diagnostics import diagnose_voice


def open_voice_settings(desktop) -> None:
    window = tk.Toplevel(desktop.root)
    window.title('Voice settings')
    window.geometry('680x570')
    window.transient(desktop.root)
    panel = ttk.Frame(window, padding=16)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Choose your voice', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='AI-generated speech. Profiles are saved on this computer.').pack(anchor='w', pady=(4, 10))
    choice = tk.StringVar(value=desktop.voice.profile)
    for name, (label, _) in PROFILES.items():
        ttk.Radiobutton(panel, text=label, variable=choice, value=name).pack(anchor='w', pady=3)
    def apply():
        try:
            desktop.voice.set_profile(choice.get())
            desktop._append('SYSTEM', f'Voice profile saved: {choice.get()}.')
        except (OSError, ValueError) as exc:
            messagebox.showerror('Voice settings', str(exc), parent=window)
    buttons = ttk.Frame(panel)
    buttons.pack(fill='x', pady=12)
    ttk.Button(buttons, text='Save profile', command=apply).pack(side='left')
    def preview(mode):
        try:
            desktop.voice.set_profile(choice.get())
            desktop.voice.test(mode)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Voice preview', str(exc), parent=window)
    for mode in ('hindi', 'hinglish', 'english'):
        ttk.Button(buttons, text=f'Test {mode}', command=lambda selected=mode: preview(selected)).pack(side='left', padx=3)
    ttk.Button(buttons, text='Stop', command=desktop.voice.stop).pack(side='left')
    output = tk.Text(panel, height=12, wrap='word', font=('Consolas', 9))
    output.pack(fill='both', expand=True)
    output.insert('1.0', 'Run diagnostics to check setup and list microphone devices. No audio is recorded.')
    output.configure(state='disabled')
    def diagnostics():
        selected = choice.get()
        check_button.configure(state='disabled')
        def show(report):
            if not window.winfo_exists():
                return
            output.configure(state='normal')
            output.delete('1.0', 'end')
            output.insert('1.0', report)
            output.configure(state='disabled')
            check_button.configure(state='normal')
        def worker():
            try:
                report = json.dumps(diagnose_voice(selected), indent=2, ensure_ascii=False)
            except Exception:
                report = 'Diagnostics unavailable. Try python -m jarvis.voice_diagnostics from the terminal.'
            try:
                desktop.root.after(0, lambda: show(report))
            except (RuntimeError, tk.TclError):
                pass
        threading.Thread(target=worker, daemon=True, name='jarvis-voice-doctor').start()
    check_button = ttk.Button(panel, text='Run local diagnostics', command=diagnostics)
    check_button.pack(anchor='w', pady=(10, 0))
