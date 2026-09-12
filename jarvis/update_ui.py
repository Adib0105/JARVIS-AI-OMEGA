"""Nonblocking, explicit release updates from the desktop."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from .config import settings
from .updater import check_latest_release, download_installer, start_installer_update


def open_update_window(root):
    owner = root.winfo_toplevel()
    desktop = getattr(root._root(), 'jarvis_desktop', None)
    existing = getattr(root._root(), '_jarvis_update_window', None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        return
    win = tk.Toplevel(owner)
    root._root()._jarvis_update_window = win
    win.title('JARVIS / Friday updates')
    body = ttk.Frame(win, padding=20)
    body.pack(fill='both', expand=True)
    status = tk.StringVar(value='Checking the latest published release…')
    ttk.Label(body, textvariable=status, wraplength=440).pack(anchor='w')
    bar = ttk.Progressbar(body, length=430)
    bar.pack(fill='x', pady=12)
    events = queue.Queue()
    state = {'result': None, 'busy': False}
    def check():
        try:
            events.put(('release', check_latest_release(settings.app_version)))
        except Exception as exc:
            events.put(('error', str(exc)))
    def install():
        if desktop is None or desktop.busy:
            messagebox.showinfo('Update', 'Finish the current reply or action before updating.', parent=win)
            return
        result = state['result']
        if not result or not result.get('asset'):
            return
        state['busy'] = True
        button.configure(state='disabled')
        status.set('Downloading verified update. JARVIS will close and reopen; your settings and data stay in place.')
        def download():
            try:
                path = download_installer(result['asset'], lambda done, total: events.put(('progress', 100*done/total)))
                events.put(('ready', path))
            except Exception as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=download, daemon=True).start()
    button = ttk.Button(body, text='UPDATE AND RESTART', command=install, state='disabled')
    button.pack(anchor='e')
    def close():
        if state['busy']:
            messagebox.showinfo('Update', 'The download is running. Please wait for it to finish.', parent=win)
        else:
            win.destroy()
    win.protocol('WM_DELETE_WINDOW', close)
    def poll():
        if not win.winfo_exists():
            return
        try:
            for _ in range(100):
                kind, value = events.get_nowait()
                if kind == 'release':
                    state['result'] = value
                    status.set(value.get('message', 'Check finished.'))
                    if value.get('available') and value.get('asset') and desktop is not None:
                        button.configure(state='normal')
                    elif value.get('available'):
                        status.set('A release exists, but its Windows installer is not published yet. Please try later.')
                elif kind == 'progress':
                    bar['value'] = value
                elif kind == 'ready':
                    # A task may have started while the download was running.
                    if desktop.busy:
                        raise RuntimeError('A task is running. Finish it, then click Update again.')
                    start_installer_update(value, state['result']['asset'])
                    desktop._exit_completely()
                    return
                elif kind == 'error':
                    raise RuntimeError(value)
        except queue.Empty:
            pass
        except Exception as exc:
            state['busy'] = False
            status.set(str(exc))
            if state['result'] and state['result'].get('asset'):
                button.configure(state='normal')
        win.after(100, poll)
    threading.Thread(target=check, daemon=True).start()
    poll()
