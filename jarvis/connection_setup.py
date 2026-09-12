"""Save and apply credentials immediately, with an optional real AI reply test."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
from .config import ROOT, settings
from .connection_manager import ConnectionInputError, read_connection_file, save_and_apply, test_connection


def open_connection_setup(desktop):
    win = tk.Toplevel(desktop.root)
    win.title('JARVIS · AI connection')
    win.transient(desktop.root)
    panel = ttk.Frame(win, padding=20)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Connect Friday to your AI provider', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='Save & Apply activates the key now. No restart needed.').pack(anchor='w', pady=8)
    provider = tk.StringVar(value=settings.provider if settings.provider in {'openrouter', 'openai'} else 'openrouter')
    chooser = ttk.Combobox(panel, textvariable=provider, values=('openrouter', 'openai'), state='readonly')
    chooser.pack(fill='x')
    key = ttk.Entry(panel, show='•', width=54)
    key.pack(fill='x', pady=10)
    ttk.Label(panel, text='Leave key blank to use the saved key for the selected provider.').pack(anchor='w')
    model = tk.StringVar(value=getattr(settings, provider.get() + '_model'))
    ttk.Label(panel, text='Model identifier:').pack(anchor='w', pady=(10, 0))
    ttk.Entry(panel, textvariable=model).pack(fill='x')
    chooser.bind('<<ComboboxSelected>>', lambda _: model.set(getattr(settings, provider.get() + '_model')))
    ttk.Label(panel, text='Changing provider clears old model-routing overrides.', wraplength=480).pack(anchor='w')
    ttk.Label(panel, text='Configuration used by THIS copy:\n' + str(ROOT / '.env'), wraplength=480).pack(anchor='w', pady=10)
    state = tk.StringVar()
    ttk.Label(panel, textvariable=state, wraplength=480).pack(anchor='w')
    def refresh():
        try:
            saved = read_connection_file()
            has_saved = bool(saved.get(provider.get().upper() + '_API_KEY'))
            state.set('Saved key: ' + ('present' if has_saved else 'not found in this folder') +
                      ' | Active connection key: ' + ('present' if settings.api_key.strip() else 'missing'))
        except (OSError, ValueError):
            state.set('Could not read configuration. Check this application folder permissions.')
    refresh()
    if (ROOT / '.env.txt').exists():
        ttk.Label(panel, text='Found .env.txt. Save & Apply writes the correct .env file.').pack(anchor='w')
    def save():
        if desktop.busy:
            state.set('Finish the current request before changing the connection.')
            return
        try:
            message = save_and_apply(desktop.jarvis, provider.get(), key.get(), model.get())
        except ConnectionInputError as exc:
            state.set(str(exc))
            return
        except Exception:
            state.set('Could not apply connection. Check folder write permission. Existing connection was kept.')
            return
        key.delete(0, 'end')
        desktop.connection_label.configure(text=f'{settings.provider.upper()}  //  {settings.model}  //  CORE {settings.app_version}')
        desktop._append('SYSTEM', message)
        state.set(message)
    results = queue.Queue()
    pending = [False]
    def test():
        if not settings.api_key.strip():
            state.set('No active key. Click SAVE & APPLY NOW first.')
            return
        if desktop.busy:
            state.set('Finish the current request first.')
            return
        pending[0] = True
        desktop._set_busy(True, 'TESTING AI', '#ffd166', 'thinking')
        state.set('Requesting one short AI reply (provider charges may apply)…')
        def worker():
            try:
                results.put(test_connection(desktop.jarvis))
            except Exception as exc:
                from .errors import classify_exception
                failure = classify_exception(exc)
                results.put('AI test failed (' + str(failure.category.value) + '). Check key/provider, model, balance or network.')
        threading.Thread(target=worker, daemon=True).start()
    def poll():
        if getattr(desktop, '_closing', False):
            return
        try:
            message = results.get_nowait()
            pending[0] = False
            desktop._set_busy(False)
            if win.winfo_exists():
                state.set(message)
        except queue.Empty:
            pass
        if win.winfo_exists() or pending[0]:
            desktop.root.after(100, poll)
    win.connection_key_entry = key
    win.connection_save_button = ttk.Button(panel, text='SAVE & APPLY NOW', command=save)
    win.connection_save_button.pack(anchor='e', pady=10)
    ttk.Button(panel, text='TEST ACTIVE CONNECTION (short AI reply)', command=test).pack(anchor='e')
    poll()
    return win
