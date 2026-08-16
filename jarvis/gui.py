from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from .config import settings
from .core import JarvisOmega
from .voice import VoiceOutput


class JarvisDesktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('JARVIS AI OMEGA V3')
        self.root.geometry('1100x720')
        self.root.minsize(850, 560)
        self.root.configure(bg='#050b12')

        self.voice = VoiceOutput()
        self.jarvis = JarvisOmega(confirmer=self._confirm_tool)
        self.busy = False

        self._build()
        self.root.protocol('WM_DELETE_WINDOW', self._close)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg='#081521', padx=18, pady=14)
        header.pack(fill='x')
        tk.Label(
            header, text='J A R V I S   O M E G A   V3',
            bg='#081521', fg='#53e7ff', font=('Segoe UI', 18, 'bold')
        ).pack(side='left')
        provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
        tk.Label(
            header, text=f'{provider}  •  {settings.model}  •  Creator: {settings.creator_name}',
            bg='#081521', fg='#9bb8c8', font=('Segoe UI', 10)
        ).pack(side='right')

        toolbar = tk.Frame(self.root, bg='#050b12', padx=14, pady=8)
        toolbar.pack(fill='x')
        self._button(toolbar, 'NEW CHAT', self._new_chat).pack(side='left', padx=4)
        self.voice_button = self._button(toolbar, 'MUTE VOICE', self._toggle_voice)
        self.voice_button.pack(side='left', padx=4)
        self._button(toolbar, 'VOICE TEST', lambda: self.voice.test('hinglish')).pack(side='left', padx=4)
        self._button(toolbar, 'STATUS', self._show_status).pack(side='left', padx=4)

        self.status = tk.Label(
            toolbar, text='READY', bg='#050b12', fg='#66ffb2', font=('Consolas', 10, 'bold')
        )
        self.status.pack(side='right', padx=8)

        self.chat = scrolledtext.ScrolledText(
            self.root, wrap='word', bg='#071019', fg='#d9f7ff', insertbackground='#53e7ff',
            selectbackground='#14445a', relief='flat', padx=18, pady=18,
            font=('Segoe UI', 11), spacing1=4, spacing3=8
        )
        self.chat.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        self.chat.tag_configure('you', foreground='#6affb8', font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('jarvis', foreground='#53e7ff', font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('body', foreground='#e6f5fa')
        self.chat.configure(state='disabled')

        bottom = tk.Frame(self.root, bg='#081521', padx=14, pady=12)
        bottom.pack(fill='x')
        self.entry = tk.Entry(
            bottom, bg='#0d1d29', fg='white', insertbackground='#53e7ff',
            relief='flat', font=('Segoe UI', 12)
        )
        self.entry.pack(side='left', fill='x', expand=True, ipady=10, padx=(0, 8))
        self.entry.bind('<Return>', lambda _event: self._send())
        self.send_button = self._button(bottom, 'SEND', self._send)
        self.send_button.pack(side='right')
        self.entry.focus_set()

        self._append('JARVIS', 'OMEGA V3 online. Type your message. Mic input is disabled; replies can be spoken.')

    @staticmethod
    def _button(parent, text: str, command):
        return tk.Button(
            parent, text=text, command=command, bg='#103346', fg='#d8f9ff',
            activebackground='#19506d', activeforeground='white', relief='flat',
            cursor='hand2', padx=12, pady=7, font=('Segoe UI', 9, 'bold')
        )

    def _append(self, speaker: str, text: str) -> None:
        self.chat.configure(state='normal')
        tag = 'you' if speaker == 'YOU' else 'jarvis'
        self.chat.insert('end', f'\n{speaker}\n', tag)
        self.chat.insert('end', f'{text}\n', 'body')
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def _confirm_tool(self, tool: str, args: dict) -> bool:
        event = threading.Event()
        result = {'allowed': False}

        def ask() -> None:
            result['allowed'] = messagebox.askyesno(
                'JARVIS Permission Gate',
                f'Allow local action?\n\nTool: {tool}\nArgs: {args}'
            )
            event.set()

        self.root.after(0, ask)
        event.wait()
        return bool(result['allowed'])

    def _send(self) -> None:
        if self.busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, 'end')
        self._append('YOU', text)
        self.busy = True
        self.status.configure(text='THINKING...', fg='#ffd166')
        self.send_button.configure(state='disabled')
        threading.Thread(target=self._answer_worker, args=(text,), daemon=True).start()

    def _answer_worker(self, text: str) -> None:
        try:
            answer = self.jarvis.chat(text)
            self.root.after(0, lambda: self._answer_done(answer, None))
        except Exception as exc:
            self.root.after(0, lambda: self._answer_done('', str(exc)))

    def _answer_done(self, answer: str, error: str | None) -> None:
        self.busy = False
        self.send_button.configure(state='normal')
        self.status.configure(text='READY', fg='#66ffb2')
        if error:
            self._append('JARVIS', f'ERROR: {error}')
            return
        self._append('JARVIS', answer)
        self.voice.speak(answer)

    def _new_chat(self) -> None:
        sid = self.jarvis.new_session()
        self._append('JARVIS', f'New session started: {sid}')

    def _toggle_voice(self) -> None:
        speaking = self.voice.toggle()
        self.voice_button.configure(text='MUTE VOICE' if speaking else 'UNMUTE VOICE')
        if speaking:
            self.voice.test('hinglish')

    def _show_status(self) -> None:
        provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
        stats = self.jarvis.memory.stats()
        messagebox.showinfo(
            'OMEGA V3 Status',
            f'Provider: {provider}\nModel: {settings.model}\nLast model: {self.jarvis.last_model_used}\n'
            f'Tool mode: {self.jarvis.last_tool_mode}\nFree web tools: {settings.enable_public_web_tools}\n'
            f'Voice: {settings.voice_engine}, pitch {settings.edge_voice_pitch}\n'
            f'Sessions: {stats["sessions"]}\nMessages: {stats["messages"]}\nKnowledge docs: {stats["knowledge_docs"]}'
        )

    def _close(self) -> None:
        self.voice.stop()
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    JarvisDesktop(root)
    root.mainloop()
