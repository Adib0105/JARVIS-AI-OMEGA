"""Repair first-run API configuration from inside the desktop."""
import tkinter as tk
from tkinter import ttk, messagebox
from dotenv import set_key
from .config import ROOT, settings


def open_connection_setup(desktop):
    win = tk.Toplevel(desktop.root)
    win.title('JARVIS · AI connection')
    win.transient(desktop.root)
    panel = ttk.Frame(win, padding=20)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Connect Friday to your AI provider', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='Paste your API key below. Save, then close and reopen JARVIS.').pack(anchor='w', pady=8)
    provider = tk.StringVar(value=settings.provider if settings.provider in {'openrouter','openai'} else 'openrouter')
    ttk.Combobox(panel, textvariable=provider, values=('openrouter','openai'), state='readonly').pack(fill='x')
    key = ttk.Entry(panel, show='•', width=54)
    key.pack(fill='x', pady=10)
    ttk.Label(panel, text='Saved beside this application:\n' + str(ROOT / '.env'), wraplength=460).pack(anchor='w')
    if (ROOT / '.env.txt').exists():
        ttk.Label(panel, text='Found .env.txt. JARVIS needs .env; Save below writes the correct file.').pack(anchor='w', pady=8)
    def save():
        value = key.get().strip()
        if not value or any(c in value for c in '\r\n\0'):
            messagebox.showerror('AI connection', 'Paste a valid single-line key.', parent=win)
            return
        try:
            path = ROOT / '.env'
            variable = 'OPENROUTER_API_KEY' if provider.get() == 'openrouter' else 'OPENAI_API_KEY'
            set_key(str(path), variable, value)
            set_key(str(path), 'AI_PROVIDER', provider.get())
        except OSError:
            messagebox.showerror('AI connection', 'Cannot save here. Extract the entire ZIP into a writable folder such as Documents, then retry.', parent=win)
            return
        key.delete(0, 'end')
        messagebox.showinfo('Saved', 'Connection saved. Exit JARVIS completely and reopen this same application.', parent=win)
        win.destroy()
    ttk.Button(panel, text='Save connection', command=save).pack(anchor='e', pady=(12,0))
