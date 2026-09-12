"""Desktop conversation library and keyboard command palette."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .workspace_commands import apply_command, search_commands


def open_command_palette(desktop):
    window = tk.Toplevel(desktop.root)
    window.title('JARVIS quick commands')
    window.geometry('600x440')
    window.transient(desktop.root)
    panel = ttk.Frame(window, padding=14)
    panel.pack(fill='both', expand=True)
    query = tk.StringVar()
    entry = ttk.Entry(panel, textvariable=query)
    entry.pack(fill='x')
    ttk.Label(panel, text='Search commands or editable prompt starters. Enter to choose.').pack(anchor='w', pady=8)
    listing = tk.Listbox(panel, font=('Segoe UI', 11), activestyle='dotbox')
    listing.pack(fill='both', expand=True)
    matches = []
    def refresh(*_):
        matches[:] = search_commands(query.get())
        listing.delete(0, 'end')
        for command in matches:
            listing.insert('end', command.label)
        if matches:
            listing.selection_set(0)
    def choose(_event=None):
        selected = listing.curselection()
        if not selected:
            return
        try:
            apply_command(desktop, matches[selected[0]].id)
            window.destroy()
        except (RuntimeError, ValueError) as exc:
            messagebox.showinfo('Quick commands', str(exc), parent=window)
    query.trace_add('write', refresh)
    listing.bind('<Double-Button-1>', choose)
    window.bind('<Return>', choose)
    window.bind('<Escape>', lambda _: window.destroy())
    ttk.Button(panel, text='Choose', command=choose).pack(anchor='e', pady=(8, 0))
    refresh()
    entry.focus_set()


def resume_chat(desktop, session_id):
    if desktop.busy:
        raise RuntimeError('Wait for the current task to finish before switching chats.')
    memory = desktop.jarvis.memory
    if memory.get_session(session_id) is None:
        raise ValueError('Chat no longer exists.')
    # Read first; a DB failure must not clear the current transcript.
    messages = memory.recent_messages(session_id, 100)
    count = memory.message_count(session_id)
    desktop.jarvis.resume_session(session_id)
    desktop._live_voice_enabled = False
    event = getattr(desktop, '_live_stop_event', None)
    if event is not None:
        event.set()
    if getattr(getattr(desktop, 'background', None), 'enabled', False):
        desktop.background.disable()
    desktop.wake_listener.stop()
    desktop.voice.stop()
    desktop._clear_images()
    desktop.chat.configure(state='normal')
    desktop.chat.delete('1.0', 'end')
    desktop.chat.configure(state='disabled')
    desktop._append('SYSTEM', f'Resumed chat: {session_id}. Showing latest {len(messages)} of {count} messages. Listening is off.')
    for role, content in messages:
        desktop._append('YOU' if role == 'user' else 'JARVIS' if role == 'assistant' else 'SYSTEM', content)
    if hasattr(desktop, 'wake_button'):
        desktop.wake_button.configure(text='WAKE WORD: OFF')
    if hasattr(desktop, 'live_voice_button'):
        desktop.live_voice_button.configure(text='LIVE: OFF')


def open_chat_library(desktop):
    window = tk.Toplevel(desktop.root)
    window.title('Saved conversations')
    window.geometry('900x600')
    window.transient(desktop.root)
    panel = ttk.Frame(window, padding=14)
    panel.pack(fill='both', expand=True)
    query = ttk.Entry(panel)
    query.pack(fill='x')
    status = tk.StringVar(value='Search titles or message text. Results stay on this computer.')
    ttk.Label(panel, textvariable=status).pack(anchor='w', pady=8)
    table = ttk.Treeview(panel, columns=('title', 'count', 'activity'), show='headings', selectmode='browse')
    for column, title, width in [('title', 'Conversation', 460), ('count', 'Messages', 80), ('activity', 'Last activity (UTC)', 200)]:
        table.heading(column, text=title)
        table.column(column, width=width)
    table.pack(fill='both', expand=True)
    generation = [0]
    def refresh(_event=None):
        generation[0] += 1
        request_id = generation[0]
        text = query.get()
        status.set('Searching saved conversations…')
        def display(rows, error=None):
            if not window.winfo_exists() or request_id != generation[0]:
                return
            if error:
                status.set(error)
                return
            for item in table.get_children():
                table.delete(item)
            for row in rows:
                table.insert('', 'end', iid=row['id'], values=(row['title'], row['message_count'], row['last_activity'][:19]))
            status.set(f'{len(rows)} conversations shown (up to 100). Select one to resume or rename.')
        def worker():
            try:
                rows = desktop.jarvis.memory.find_sessions(text)
                callback = lambda: display(rows)
            except Exception:
                callback = lambda: display([], 'Could not load conversations. Retry after the current task finishes.')
            try:
                desktop.root.after(0, callback)
            except (RuntimeError, tk.TclError):
                pass
        threading.Thread(target=worker, daemon=True, name='jarvis-chat-search').start()
    def selected():
        ids = table.selection()
        if not ids:
            raise ValueError('Select a conversation first.')
        return ids[0]
    def resume():
        try:
            resume_chat(desktop, selected())
            window.destroy()
        except (RuntimeError, ValueError) as exc:
            messagebox.showinfo('Saved conversations', str(exc), parent=window)
    def rename():
        try:
            sid = selected()
            title = simpledialog.askstring('Rename conversation', 'New title (1–100 characters):', initialvalue=table.item(sid, 'values')[0], parent=window)
            if title is not None:
                desktop.jarvis.memory.rename_session(sid, title)
                refresh()
        except (RuntimeError, ValueError) as exc:
            messagebox.showinfo('Saved conversations', str(exc), parent=window)
    buttons = ttk.Frame(panel)
    buttons.pack(fill='x', pady=(10, 0))
    for label, command in [('Search / refresh', refresh), ('Resume selected', resume), ('Rename', rename)]:
        ttk.Button(buttons, text=label, command=command).pack(side='left', padx=(0, 8))
    query.bind('<Return>', refresh)
    table.bind('<Double-Button-1>', lambda _: resume())
    refresh()
    query.focus_set()


def install_chat_workspace():
    from .gui import JarvisDesktop
    from .voice_settings_ui import open_voice_settings
    if getattr(JarvisDesktop, '_chat_workspace_installed', False):
        return
    original = JarvisDesktop.__init__
    def init(self, root):
        original(self, root)
        root.bind('<Control-k>', lambda _: open_command_palette(self))
        root.bind('<Control-h>', lambda _: open_chat_library(self))
        bar = tk.Frame(root, bg='#061725', padx=12, pady=4)
        bar.pack(side='bottom', fill='x')
        for label, command in [('QUICK COMMANDS · Ctrl+K', lambda: open_command_palette(self)), ('SAVED CHATS · Ctrl+H', lambda: open_chat_library(self))]:
            ttk.Button(bar, text=label, command=command).pack(side='left', padx=4)
    JarvisDesktop.__init__ = init
    JarvisDesktop._chat_library = open_chat_library
    JarvisDesktop._voice_preferences = open_voice_settings
    JarvisDesktop._chat_workspace_installed = True
