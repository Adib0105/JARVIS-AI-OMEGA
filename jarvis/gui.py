from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

from PIL import Image, ImageTk

from .attachments import image_info, normalize_image_paths, save_clipboard_image, validate_image
from .config import settings
from .core import JarvisOmega
from .hud import ArcReactorHUD
from .microphone import WakeWordListener, record_and_transcribe
from .settings_ui import show_settings_dialog, show_update_dialog
from .system_tools import system_metrics
from .vision import capture_screen
from .voice import VoiceOutput


BG = '#030810'
PANEL = '#07131d'
PANEL_2 = '#091a26'
CYAN = '#53e7ff'
CYAN_DIM = '#1d5368'
GREEN = '#6affb8'
GOLD = '#ffd166'
MAGENTA = '#d98cff'
RED = '#ff5c73'
TEXT = '#dff9ff'
MUTED = '#86a8b8'


class JarvisDesktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('JARVIS AI OMEGA V6 // ARC DESKTOP AGENT')
        self.root.geometry('1440x900')
        self.root.minsize(1120, 720)
        self.root.configure(bg=BG)

        self.hud: ArcReactorHUD | None = None
        self.voice = VoiceOutput(on_state_change=self._voice_state_changed)
        self.jarvis = JarvisOmega(confirmer=self._confirm_tool)
        self.busy = False
        self.attached_images: list[Path] = []
        self._preview_ref = None
        self.wake_listener = WakeWordListener(
            on_command=self._wake_command,
            on_state=self._wake_state,
            on_error=self._wake_error,
            wake_word=settings.wake_word,
            language=settings.speech_language,
        )
        self.metric_vars: dict[str, tk.StringVar] = {}
        self.todo_ids: list[int] = []

        self._build()
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        self.root.bind('<Control-o>', lambda _e: self._upload_images())
        self.root.bind('<Control-l>', lambda _e: self.entry.focus_set())
        self.root.bind('<Control-m>', lambda _e: self._push_to_talk())
        self.root.bind('<F2>', lambda _e: self._mission())

        self._refresh_metrics()
        self._refresh_tasks()
        self._poll_reminders()
        if settings.enable_wake_word and settings.enable_mic_input:
            self._toggle_wake_word()

    def _build(self) -> None:
        self._build_header()
        self._build_input_bar()

        main = tk.Frame(self.root, bg=BG)
        main.pack(side='top', fill='both', expand=True, padx=10, pady=(6, 10))

        left = tk.Frame(main, bg=PANEL, width=260, highlightbackground=CYAN_DIM, highlightthickness=1)
        left.pack(side='left', fill='y', padx=(0, 8))
        left.pack_propagate(False)
        self._build_left_panel(left)

        right = tk.Frame(main, bg=PANEL, width=285, highlightbackground=CYAN_DIM, highlightthickness=1)
        right.pack(side='right', fill='y', padx=(8, 0))
        right.pack_propagate(False)
        self._build_right_panel(right)

        center = tk.Frame(main, bg=BG)
        center.pack(side='left', fill='both', expand=True)
        self._build_center(center)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg='#061725', padx=18, pady=12)
        header.pack(side='top', fill='x')

        title_box = tk.Frame(header, bg='#061725')
        title_box.pack(side='left')
        tk.Label(
            title_box,
            text='J A R V I S   O M E G A   V6',
            bg='#061725', fg=CYAN, font=('Segoe UI', 19, 'bold'),
        ).pack(anchor='w')
        tk.Label(
            title_box,
            text='ARC DESKTOP AGENT // MULTIMODAL INTELLIGENCE SYSTEM',
            bg='#061725', fg=MUTED, font=('Consolas', 8, 'bold'),
        ).pack(anchor='w')

        operator = tk.Frame(header, bg='#061725')
        operator.pack(side='right')
        provider = 'OPENROUTER FREE' if settings.provider == 'openrouter' else 'OPENAI'
        tk.Label(
            operator,
            text=f'OPERATOR: {settings.creator_name.upper()}',
            bg='#061725', fg=GREEN, font=('Consolas', 11, 'bold'),
        ).pack(anchor='e')
        tk.Label(
            operator,
            text=f'{provider}  //  {settings.model}  //  CORE {settings.app_version}',
            bg='#061725', fg=MUTED, font=('Consolas', 8),
        ).pack(anchor='e')

    def _build_input_bar(self) -> None:
        bottom = tk.Frame(self.root, bg='#061725', padx=14, pady=11)
        bottom.pack(side='bottom', fill='x')

        self.entry = tk.Entry(
            bottom,
            bg='#0a202e', fg='white', insertbackground=CYAN,
            relief='flat', font=('Segoe UI', 12),
        )
        self.entry.pack(side='left', fill='x', expand=True, ipady=11, padx=(0, 8))
        self.entry.bind('<Return>', lambda _event: self._send())

        self.mic_button = self._button(bottom, 'MIC / CTRL+M', self._push_to_talk, MAGENTA)
        self.mic_button.pack(side='right', padx=(4, 0))
        self.send_button = self._button(bottom, 'SEND', self._send, CYAN)
        self.send_button.pack(side='right', padx=(4, 0))
        self.entry.focus_set()

    def _build_left_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text='ARC CORE', bg=PANEL, fg=CYAN, font=('Consolas', 10, 'bold')).pack(pady=(12, 2))
        self.hud = ArcReactorHUD(parent, size=220, bg=PANEL)
        self.hud.pack(pady=(0, 6))

        metrics = tk.Frame(parent, bg=PANEL_2, padx=10, pady=8)
        metrics.pack(fill='x', padx=10, pady=(2, 8))
        tk.Label(metrics, text='LIVE SYSTEM TELEMETRY', bg=PANEL_2, fg=GOLD, font=('Consolas', 8, 'bold')).pack(anchor='w')
        for key, label in [
            ('cpu', 'CPU'), ('ram', 'MEMORY'), ('disk', 'DISK'), ('battery', 'BATTERY'), ('processes', 'PROCESSES')
        ]:
            var = tk.StringVar(value=f'{label}: --')
            self.metric_vars[key] = var
            tk.Label(metrics, textvariable=var, bg=PANEL_2, fg=TEXT, font=('Consolas', 8)).pack(anchor='w', pady=1)

        tk.Label(parent, text='QUICK CONTROL', bg=PANEL, fg=CYAN, font=('Consolas', 9, 'bold')).pack(pady=(2, 5))
        quick = tk.Frame(parent, bg=PANEL)
        quick.pack(fill='x', padx=10)
        for text, command, color in [
            ('NEW CHAT', self._new_chat, CYAN),
            ('MISSION  F2', self._mission, GOLD),
            ('SCREEN VISION', self._screen_vision, MAGENTA),
            ('UPLOAD IMAGE', self._upload_images, MAGENTA),
            ('PASTE IMAGE', self._paste_image, MAGENTA),
            ('BROWSER SEARCH', self._quick_browser, CYAN),
            ('OPEN APP', self._quick_app, CYAN),
        ]:
            self._button(quick, text, command, color).pack(fill='x', pady=2)

        self.wake_button = self._button(parent, 'WAKE WORD: OFF', self._toggle_wake_word, GREEN)
        self.wake_button.pack(fill='x', padx=10, pady=(8, 4))
        tk.Label(
            parent,
            text=f'Wake phrase: “{settings.wake_word}”\nPush-to-talk works independently.',
            bg=PANEL, fg=MUTED, font=('Segoe UI', 8), justify='left', wraplength=225,
        ).pack(anchor='w', padx=12, pady=(0, 10))

    def _build_right_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text='MISSION / PRODUCTIVITY', bg=PANEL, fg=CYAN, font=('Consolas', 10, 'bold')).pack(pady=(12, 6))

        task_frame = tk.Frame(parent, bg=PANEL_2, padx=8, pady=8)
        task_frame.pack(fill='x', padx=10)
        tk.Label(task_frame, text='ACTIVE TASKS', bg=PANEL_2, fg=GOLD, font=('Consolas', 8, 'bold')).pack(anchor='w')
        self.todo_list = tk.Listbox(
            task_frame, height=7, bg='#06111a', fg=TEXT, selectbackground='#12445b',
            highlightthickness=0, relief='flat', font=('Segoe UI', 9),
        )
        self.todo_list.pack(fill='x', pady=(5, 6))
        row = tk.Frame(task_frame, bg=PANEL_2)
        row.pack(fill='x')
        self._button(row, '+ TODO', self._add_todo, GREEN).pack(side='left', fill='x', expand=True, padx=(0, 2))
        self._button(row, 'DONE', self._complete_todo, GOLD).pack(side='left', fill='x', expand=True, padx=(2, 0))
        self._button(task_frame, '+ REMINDER', self._add_reminder, MAGENTA).pack(fill='x', pady=(5, 0))

        tk.Label(parent, text='INTELLIGENCE MODULES', bg=PANEL, fg=CYAN, font=('Consolas', 9, 'bold')).pack(pady=(10, 4))
        modules = tk.Frame(parent, bg=PANEL)
        modules.pack(fill='x', padx=10)
        for text, command, color in [
            ('LEARN DOCUMENT', self._learn_document, MAGENTA),
            ('RUN CODE TESTS', self._code_tests, GOLD),
            ('EXPORT CHAT', self._export_chat, CYAN),
            ('VOICE TEST', lambda: self.voice.test('hinglish'), GREEN),
            ('MUTE / UNMUTE', self._toggle_voice, GREEN),
            ('IMAGE HELP', self._image_help, MAGENTA),
            ('SYSTEM STATUS', self._show_status, CYAN),
            ('SETTINGS', self._open_settings, GREEN),
            ('CHECK UPDATE', self._check_update, GOLD),
        ]:
            self._button(modules, text, command, color).pack(fill='x', pady=1)

        self.status = tk.Label(
            parent,
            text='● READY', bg=PANEL, fg=GREEN, font=('Consolas', 10, 'bold'),
        )
        self.status.pack(side='bottom', pady=10)

    def _build_center(self, parent: tk.Frame) -> None:
        self.attachment_frame = tk.Frame(parent, bg=PANEL_2, padx=10, pady=7)
        self.attachment_frame.pack(side='top', fill='x', pady=(0, 7))
        self.preview_label = tk.Label(
            self.attachment_frame,
            text='NO IMAGE ATTACHED  //  CTRL+O TO UPLOAD',
            bg=PANEL_2, fg=MUTED, font=('Consolas', 8),
        )
        self.preview_label.pack(side='left', fill='x', expand=True)
        self.clear_images_button = self._button(self.attachment_frame, 'CLEAR', self._clear_images, RED)
        self.clear_images_button.pack(side='right')

        self.chat = scrolledtext.ScrolledText(
            parent,
            wrap='word', bg='#04101a', fg=TEXT, insertbackground=CYAN,
            selectbackground='#14445a', relief='flat', padx=18, pady=16,
            font=('Segoe UI', 11), spacing1=4, spacing3=8,
        )
        self.chat.pack(side='top', fill='both', expand=True)
        self.chat.tag_configure('you', foreground=GREEN, font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('jarvis', foreground=CYAN, font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('system', foreground=GOLD, font=('Segoe UI', 9, 'bold'))
        self.chat.tag_configure('mission', foreground=MAGENTA, font=('Consolas', 9, 'bold'))
        self.chat.tag_configure('body', foreground=TEXT)
        self.chat.configure(state='disabled')
        self._append(
            'JARVIS',
            f'OMEGA V6 ARC core online. Welcome, {settings.creator_name}. Type, use MIC, attach images, '
            'run a Mission, inspect documents, or use approved desktop tools. All sensitive local actions stay permission-gated.'
        )

    @staticmethod
    def _button(parent, text: str, command, accent: str = CYAN):
        return tk.Button(
            parent,
            text=text, command=command,
            bg='#0b2a3a', fg=accent,
            activebackground='#12445b', activeforeground='white',
            relief='flat', cursor='hand2', padx=9, pady=6,
            font=('Segoe UI', 8, 'bold'),
            highlightthickness=1, highlightbackground='#123f51',
        )

    def _append(self, speaker: str, text: str) -> None:
        self.chat.configure(state='normal')
        if speaker == 'YOU':
            tag = 'you'
        elif speaker == 'SYSTEM':
            tag = 'system'
        elif speaker == 'MISSION':
            tag = 'mission'
        else:
            tag = 'jarvis'
        self.chat.insert('end', f'\n{speaker}\n', tag)
        self.chat.insert('end', f'{text}\n', 'body')
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def _set_hud(self, state: str) -> None:
        if self.hud:
            self.hud.set_state(state)

    def _voice_state_changed(self, state: str) -> None:
        try:
            self.root.after(0, lambda: self._set_hud(state))
        except Exception:
            pass

    def _set_busy(self, busy: bool, label: str = 'READY', color: str = GREEN, hud_state: str | None = None) -> None:
        self.busy = busy
        if hasattr(self, 'status'):
            self.status.configure(text=f'● {label}', fg=color)
        if hasattr(self, 'send_button'):
            self.send_button.configure(state='disabled' if busy else 'normal')
        if hud_state:
            self._set_hud(hud_state)
        elif not busy:
            self._set_hud('idle')

    def _confirm_tool(self, tool: str, args: dict) -> bool:
        event = threading.Event()
        result = {'allowed': False}

        def ask() -> None:
            result['allowed'] = messagebox.askyesno(
                'JARVIS V6 // Permission Gate',
                f'Allow this local action?\n\nTool: {tool}\n\nArguments:\n{args}\n\n'
                'Only approve if this matches what you asked JARVIS to do.'
            )
            event.set()

        self.root.after(0, ask)
        event.wait()
        return bool(result['allowed'])

    def _refresh_metrics(self) -> None:
        try:
            metrics = system_metrics()
            if metrics.get('available') is False:
                values = {'cpu': '--', 'ram': '--', 'disk': '--', 'battery': '--', 'processes': '--'}
            else:
                battery = metrics.get('battery_percent')
                battery_text = '--' if battery is None else f'{battery:.0f}%'
                if metrics.get('battery_plugged'):
                    battery_text += ' ⚡'
                values = {
                    'cpu': f"{metrics.get('cpu_percent', 0):.1f}%",
                    'ram': f"{metrics.get('memory_percent', 0):.1f}%",
                    'disk': f"{metrics.get('disk_percent', 0):.1f}%",
                    'battery': battery_text,
                    'processes': str(metrics.get('processes', '--')),
                }
            labels = {'cpu': 'CPU', 'ram': 'MEMORY', 'disk': 'DISK', 'battery': 'BATTERY', 'processes': 'PROCESSES'}
            for key, value in values.items():
                if key in self.metric_vars:
                    self.metric_vars[key].set(f'{labels[key]}: {value}')
        finally:
            self.root.after(max(700, settings.system_refresh_ms), self._refresh_metrics)

    def _refresh_tasks(self) -> None:
        if not hasattr(self, 'todo_list'):
            return
        rows = self.jarvis.memory.list_todos(False, 30)
        self.todo_list.delete(0, 'end')
        self.todo_ids = []
        for row in rows:
            self.todo_ids.append(int(row['id']))
            title = row['title']
            self.todo_list.insert('end', f"#{row['id']}  {title[:42]}")
        if not rows:
            self.todo_list.insert('end', 'No active tasks')

    def _add_todo(self) -> None:
        title = simpledialog.askstring('Add Todo', 'Task kya hai?')
        if not title:
            return
        try:
            todo = self.jarvis.memory.add_todo(title)
            self._append('SYSTEM', f"Todo #{todo['id']} added: {todo['title']}")
            self._refresh_tasks()
        except Exception as exc:
            messagebox.showerror('Todo', str(exc))

    def _complete_todo(self) -> None:
        selected = self.todo_list.curselection()
        if not selected or not self.todo_ids:
            return
        index = selected[0]
        if index >= len(self.todo_ids):
            return
        todo_id = self.todo_ids[index]
        result = self.jarvis.memory.complete_todo(todo_id)
        if result['completed']:
            self._append('SYSTEM', f'Todo #{todo_id} completed.')
        self._refresh_tasks()

    def _add_reminder(self) -> None:
        text = simpledialog.askstring('Reminder', 'Reminder message:')
        if not text:
            return
        due = simpledialog.askstring('Reminder Time', 'Local time: YYYY-MM-DD HH:MM\nExample: 2026-08-16 18:30')
        if not due:
            return
        try:
            dt = datetime.strptime(due.strip(), '%Y-%m-%d %H:%M').astimezone()
            reminder = self.jarvis.memory.add_reminder(text, dt.isoformat())
            self._append('SYSTEM', f"Reminder #{reminder['id']} scheduled for {dt.strftime('%d %b %Y, %I:%M %p')}.")
        except Exception as exc:
            messagebox.showerror('Reminder', str(exc))

    def _poll_reminders(self) -> None:
        try:
            due = self.jarvis.memory.due_reminders(10)
            for reminder in due:
                self.jarvis.memory.mark_reminder_done(reminder['id'])
                message = f"REMINDER: {reminder['text']}"
                self._append('SYSTEM', message)
                self.voice.speak(message)
                self.root.bell()
        finally:
            delay = max(2, int(settings.reminder_poll_seconds)) * 1000
            self.root.after(delay, self._poll_reminders)

    def _refresh_attachment_bar(self) -> None:
        self._preview_ref = None
        if not self.attached_images:
            self.preview_label.configure(image='', compound='left', text='NO IMAGE ATTACHED  //  CTRL+O TO UPLOAD', fg=MUTED)
            return

        first = self.attached_images[0]
        names = ', '.join(path.name for path in self.attached_images[:3])
        if len(self.attached_images) > 3:
            names += f' +{len(self.attached_images) - 3} more'
        try:
            with Image.open(first) as image:
                preview = image.convert('RGB')
                preview.thumbnail((62, 44), Image.Resampling.LANCZOS)
                self._preview_ref = ImageTk.PhotoImage(preview)
            info = image_info(first)
            suffix = f" // {info['width']}x{info['height']} // {info['size_mb']} MB"
            self.preview_label.configure(
                image=self._preview_ref, compound='left',
                text=f'  {len(self.attached_images)} IMAGE(S): {names}{suffix}', fg=TEXT,
            )
        except Exception:
            self.preview_label.configure(image='', text=f'{len(self.attached_images)} IMAGE(S): {names}', fg=TEXT)

    def _upload_images(self) -> None:
        if self.busy:
            return
        selected = filedialog.askopenfilenames(
            title=f'JARVIS V6 // Upload up to {settings.max_image_attachments} images',
            filetypes=[
                ('Supported images', '*.png *.jpg *.jpeg *.webp'),
                ('PNG', '*.png'), ('JPEG', '*.jpg *.jpeg'), ('WEBP', '*.webp'),
            ],
        )
        if not selected:
            return
        try:
            self.attached_images = normalize_image_paths(list(selected))
            self._refresh_attachment_bar()
            self._append('SYSTEM', 'Image attachment loaded. Type a question and press SEND.')
            self.entry.focus_set()
        except Exception as exc:
            messagebox.showerror('Image Upload', str(exc))

    def _paste_image(self) -> None:
        if self.busy:
            return
        try:
            path = save_clipboard_image()
            validate_image(path)
            self.attached_images = [path]
            self._refresh_attachment_bar()
            self._append('SYSTEM', f'Clipboard image attached: {path.name}')
        except Exception as exc:
            messagebox.showerror('Paste Image', str(exc))

    def _clear_images(self) -> None:
        self.attached_images = []
        self._refresh_attachment_bar()

    def _send(self) -> None:
        self._send_text(self.entry.get().strip(), list(self.attached_images), from_voice=False)

    def _send_text(self, text: str, images: list[Path] | None = None, from_voice: bool = False) -> None:
        if self.busy:
            return
        images = images or []
        if not text and not images:
            return
        self.entry.delete(0, 'end')
        prompt = text or 'Analyze the attached image(s) carefully and tell me the important details.'
        if images:
            names = ', '.join(path.name for path in images)
            self._append('YOU', f'{prompt}\n[Attached: {names}]')
            self._set_busy(True, 'IMAGE AI', MAGENTA, 'thinking')
        else:
            self._append('YOU', f'[VOICE] {prompt}' if from_voice else prompt)
            self._set_busy(True, 'THINKING', GOLD, 'thinking')
        threading.Thread(target=self._answer_worker, args=(prompt, images), daemon=True).start()

    def _answer_worker(self, text: str, images: list[Path]) -> None:
        try:
            answer = self.jarvis.analyze_images(images, text) if images else self.jarvis.chat(text)
            self.root.after(0, lambda: self._answer_done(answer, None, bool(images)))
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda error=error: self._answer_done('', error, False))

    def _answer_done(self, answer: str, error: str | None, clear_images: bool) -> None:
        self._set_busy(False)
        if error:
            self._set_hud('error')
            self._append('JARVIS', f'ERROR: {error}')
            self.root.after(1800, lambda: self._set_hud('idle'))
            return
        self._append('JARVIS', answer)
        if clear_images:
            self._clear_images()
        self.voice.speak(answer)
        self._refresh_tasks()

    def _mission(self) -> None:
        if self.busy:
            return
        goal = simpledialog.askstring(
            'JARVIS V6 Mission',
            'Mission goal kya hai?\nPlanner → Executor → Reviewer mode chalega.',
        )
        if not goal:
            return
        self._append('MISSION', f'GOAL: {goal}')
        self._set_busy(True, 'MISSION', MAGENTA, 'thinking')
        threading.Thread(target=self._mission_worker, args=(goal,), daemon=True).start()

    def _mission_worker(self, goal: str) -> None:
        def progress(message: str) -> None:
            self.root.after(0, lambda m=message: self._append('MISSION', m))
        try:
            result = self.jarvis.run_mission(goal, progress)
            self.root.after(0, lambda: self._mission_done(result, None))
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda error=error: self._mission_done('', error))

    def _mission_done(self, result: str, error: str | None) -> None:
        self._set_busy(False)
        if error:
            self._append('JARVIS', f'MISSION ERROR: {error}')
            self._set_hud('error')
            self.root.after(1800, lambda: self._set_hud('idle'))
            return
        self._append('JARVIS', f'MISSION REVIEW\n{result}')
        self.voice.speak(result)
        self._refresh_tasks()

    def _push_to_talk(self) -> None:
        if self.busy or not settings.enable_mic_input:
            if not settings.enable_mic_input:
                messagebox.showinfo('Microphone', 'ENABLE_MIC_INPUT=false in .env.')
            return
        self._set_busy(True, 'LISTENING', MAGENTA, 'listening')
        threading.Thread(target=self._mic_worker, daemon=True).start()

    def _mic_worker(self) -> None:
        try:
            text = record_and_transcribe(settings.mic_record_seconds, settings.speech_language)
            self.root.after(0, lambda: self._mic_done(text, None))
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda error=error: self._mic_done('', error))

    def _mic_done(self, text: str, error: str | None) -> None:
        self._set_busy(False)
        if error:
            self._append('SYSTEM', f'MIC: {error}')
            return
        if not text:
            return
        self.entry.delete(0, 'end')
        self.entry.insert(0, text)
        self._send_text(text, from_voice=True)

    def _toggle_wake_word(self) -> None:
        if not settings.enable_mic_input:
            messagebox.showinfo('Wake Word', 'Microphone input is disabled in .env.')
            return
        if self.wake_listener.running:
            self.wake_listener.stop()
            self.wake_button.configure(text='WAKE WORD: OFF', fg=GREEN)
            self._append('SYSTEM', 'Wake-word listener stopped.')
        else:
            self.wake_listener.start()
            self.wake_button.configure(text='WAKE WORD: ON', fg=MAGENTA)
            self._append('SYSTEM', f'Wake-word listener enabled: “{settings.wake_word}”.')

    def _wake_command(self, command: str) -> None:
        self.root.after(0, lambda: self._send_text(command, from_voice=True))

    def _wake_state(self, state: str) -> None:
        if state == 'listening':
            self.root.after(0, lambda: self._set_hud('listening'))
        elif state == 'idle':
            self.root.after(0, lambda: self._set_hud('idle'))

    def _wake_error(self, message: str) -> None:
        if 'clear nahi' in message.lower():
            return
        self.root.after(0, lambda: self.status.configure(text='● WAKE RETRY', fg=GOLD))

    def _screen_vision(self) -> None:
        if self.busy:
            return
        prompt = simpledialog.askstring(
            'Screen Vision',
            'What should JARVIS inspect?',
            initialvalue='Analyze my screen, identify any errors or important UI state, and tell me what to do next.',
        )
        if prompt is None:
            return
        if not messagebox.askyesno(
            'Screen Capture Permission',
            'Allow JARVIS to capture the current screen and send the processed screenshot to the configured AI provider?',
        ):
            return
        self._set_busy(True, f'VISION ≤{int(settings.vision_timeout_seconds)}s', MAGENTA, 'thinking')
        threading.Thread(target=self._vision_worker, args=(prompt,), daemon=True).start()

    def _vision_worker(self, prompt: str) -> None:
        try:
            screenshot = capture_screen()
            answer = self.jarvis.analyze_image(screenshot, prompt)
            self.root.after(0, lambda: self._vision_done(answer, screenshot.name, None))
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda error=error: self._vision_done('', '', error))

    def _vision_done(self, answer: str, name: str, error: str | None) -> None:
        self._set_busy(False)
        if error:
            self._append('JARVIS', f'SCREEN VISION ERROR: {error}')
            return
        self._append('JARVIS', f'[Screen: {name}]\n{answer}')
        self.voice.speak(answer)

    def _learn_document(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title='JARVIS V6 // Learn document',
            filetypes=[
                ('Documents', '*.pdf *.docx *.xlsx *.xlsm *.csv *.txt *.md'),
                ('PDF', '*.pdf'), ('Word', '*.docx'), ('Excel', '*.xlsx *.xlsm'),
                ('Text/CSV', '*.txt *.md *.csv'),
            ],
        )
        if path:
            self._run_tool_async('index_document', {'file_path': path}, 'LEARNING DOC')

    def _code_tests(self) -> None:
        if self.busy:
            return
        folder = filedialog.askdirectory(title='Select approved Python project folder with tests/')
        if folder:
            self._run_tool_async('run_project_tests', {'project_dir': folder, 'timeout': 180}, 'TESTING')

    def _quick_browser(self) -> None:
        if self.busy:
            return
        query = simpledialog.askstring('Browser Search', 'Search kya karna hai?')
        if not query:
            return
        engine = simpledialog.askstring('Search Engine', 'google / youtube / github / bing', initialvalue='google') or 'google'
        self._run_tool_async('browser_search', {'query': query, 'engine': engine.lower()}, 'BROWSER')

    def _quick_app(self) -> None:
        if self.busy:
            return
        app = simpledialog.askstring('Open App', 'notepad / calculator / explorer / paint / vscode / chrome / edge / taskmgr')
        if app:
            self._run_tool_async('open_app', {'app': app}, 'APP')

    def _run_tool_async(self, name: str, args: dict, label: str) -> None:
        self._set_busy(True, label, GOLD, 'thinking')

        def worker() -> None:
            result = self.jarvis.tools.call(name, args)
            self.root.after(0, lambda: self._tool_done(name, result))

        threading.Thread(target=worker, daemon=True).start()

    def _tool_done(self, name: str, result: str) -> None:
        self._set_busy(False)
        self._append('SYSTEM', f'{name}:\n{result}')
        self._refresh_tasks()

    def _toggle_voice(self) -> None:
        speaking = self.voice.toggle()
        self._append('SYSTEM', 'Spoken replies enabled.' if speaking else 'Spoken replies muted.')
        if speaking:
            self.voice.test('hinglish')

    def _export_chat(self) -> None:
        try:
            target = self.jarvis.memory.export_session(self.jarvis.session_id, settings.export_dir)
            self._append('SYSTEM', f'Chat exported to:\n{target}')
        except Exception as exc:
            messagebox.showerror('Export Chat', str(exc))

    def _new_chat(self) -> None:
        if self.busy:
            return
        sid = self.jarvis.new_session()
        self._clear_images()
        self._append('JARVIS', f'New V6 session started: {sid}')

    def _open_settings(self) -> None:
        if self.busy:
            return
        show_settings_dialog(self.root, on_saved=lambda: self._append('SYSTEM', 'Settings saved. Restart JARVIS to apply all changes.'))

    def _check_update(self) -> None:
        if self.busy:
            return
        show_update_dialog(self.root)

    def _image_help(self) -> None:
        messagebox.showinfo(
            'JARVIS V6 // Image Intelligence',
            'UPLOAD IMAGE / Ctrl+O: select up to 4 PNG/JPG/JPEG/WEBP files.\n\n'
            'PASTE IMAGE: attach an image copied to the Windows clipboard.\n\n'
            'SCREEN VISION: captures the current desktop only after permission.\n\n'
            'After attaching, type your question and press SEND. If text is empty, JARVIS performs general analysis.\n\n'
            'Images are validated/resized locally, then sent to your configured AI provider for analysis. '
            'Do not include passwords, API keys, banking data, or recovery codes in screenshots.'
        )

    def _show_status(self) -> None:
        provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
        stats = self.jarvis.memory.stats()
        messagebox.showinfo(
            'OMEGA V6 // Core Status',
            f'Version: {settings.app_version}\n'
            f'Operator / Creator: {settings.creator_name}\n'
            f'Provider: {provider}\nModel: {settings.model}\nLast model: {self.jarvis.last_model_used}\n'
            f'Last request: {self.jarvis.last_request_kind}\nTool mode: {self.jarvis.last_tool_mode}\n'
            f'Desktop automation: {settings.enable_desktop_automation}\n'
            f'Document intelligence: {settings.enable_document_intelligence}\n'
            f'Coding tools: {settings.enable_coding_tools}\n'
            f'Microphone: {settings.enable_mic_input}\nWake listener running: {self.wake_listener.running}\n'
            f'Voice: {settings.voice_engine}, pitch {settings.edge_voice_pitch}\n'
            f'Image upload: True ({settings.max_image_attachments} max)\nScreen vision: True\n'
            f'AI timeout: {settings.ai_timeout_seconds}s\nVision timeout: {settings.vision_timeout_seconds}s\n'
            f'Sessions: {stats["sessions"]}\nMessages: {stats["messages"]}\nFacts: {stats["facts"]}\n'
            f'Knowledge docs: {stats["knowledge_docs"]}\nOpen todos: {stats["open_todos"]}\n'
            f'Pending reminders: {stats["pending_reminders"]}\nLast latency: {self.jarvis.last_latency:.2f}s'
        )

    def _close(self) -> None:
        self.wake_listener.stop()
        self.voice.stop()
        if self.hud:
            self.hud.stop()
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    JarvisDesktop(root)
    root.mainloop()
