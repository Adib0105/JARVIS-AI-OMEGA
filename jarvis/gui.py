from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

from PIL import Image, ImageTk

from .attachments import image_info, normalize_image_paths, save_clipboard_image, validate_image
from .config import settings
from .core import JarvisOmega
from .vision import capture_screen
from .voice import VoiceOutput


class JarvisDesktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f'JARVIS AI OMEGA V{settings.app_version.split(".")[0]}')
        self.root.geometry('1180x780')
        self.root.minsize(900, 620)
        self.root.configure(bg='#050b12')

        self.voice = VoiceOutput()
        self.jarvis = JarvisOmega(confirmer=self._confirm_tool)
        self.busy = False
        self.attached_images: list[Path] = []
        self._preview_ref = None

        self._build()
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        self.root.bind('<Control-o>', lambda _e: self._upload_images())
        self.root.bind('<Control-l>', lambda _e: self.entry.focus_set())

    def _build(self) -> None:
        header = tk.Frame(self.root, bg='#081521', padx=18, pady=14)
        header.pack(side='top', fill='x')
        tk.Label(
            header, text='J A R V I S   O M E G A   V5',
            bg='#081521', fg='#53e7ff', font=('Segoe UI', 18, 'bold')
        ).pack(side='left')
        provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
        tk.Label(
            header,
            text=f'{provider}  •  {settings.model}  •  Creator: {settings.creator_name}',
            bg='#081521', fg='#9bb8c8', font=('Segoe UI', 10)
        ).pack(side='right')

        toolbar = tk.Frame(self.root, bg='#050b12', padx=12, pady=7)
        toolbar.pack(side='top', fill='x')
        for text, command in [
            ('NEW CHAT', self._new_chat),
            ('UPLOAD IMAGE', self._upload_images),
            ('PASTE IMAGE', self._paste_image),
            ('SCREEN VISION', self._screen_vision),
            ('LEARN FILE', self._learn_file),
        ]:
            self._button(toolbar, text, command).pack(side='left', padx=3)

        # Frame internal padding must be a single screen-distance value.
        # Tuple spacing belongs on geometry managers such as pack(), not tk.Frame(pady=...).
        toolbar2 = tk.Frame(self.root, bg='#050b12', padx=12, pady=7)
        toolbar2.pack(side='top', fill='x', pady=(0, 7))
        self.voice_button = self._button(toolbar2, 'MUTE VOICE', self._toggle_voice)
        self.voice_button.pack(side='left', padx=3)
        for text, command in [
            ('VOICE TEST', lambda: self.voice.test('hinglish')),
            ('EXPORT CHAT', self._export_chat),
            ('IMAGE HELP', self._image_help),
            ('STATUS', self._show_status),
        ]:
            self._button(toolbar2, text, command).pack(side='left', padx=3)

        self.status = tk.Label(
            toolbar2, text='READY', bg='#050b12', fg='#66ffb2', font=('Consolas', 10, 'bold')
        )
        self.status.pack(side='right', padx=8)

        self.attachment_frame = tk.Frame(self.root, bg='#09131d', padx=12, pady=8)
        self.attachment_frame.pack(side='top', fill='x', padx=12, pady=(0, 7))
        self.preview_label = tk.Label(
            self.attachment_frame,
            text='No image attached • Ctrl+O to upload',
            bg='#09131d', fg='#8aa6b5', font=('Segoe UI', 9)
        )
        self.preview_label.pack(side='left', fill='x', expand=True)
        self.clear_images_button = self._button(self.attachment_frame, 'CLEAR IMAGES', self._clear_images)
        self.clear_images_button.pack(side='right', padx=4)

        # Pack input first so the expanding chat panel can never push it off-screen.
        bottom = tk.Frame(self.root, bg='#081521', padx=14, pady=12)
        bottom.pack(side='bottom', fill='x')
        self.entry = tk.Entry(
            bottom, bg='#0d1d29', fg='white', insertbackground='#53e7ff',
            relief='flat', font=('Segoe UI', 12)
        )
        self.entry.pack(side='left', fill='x', expand=True, ipady=10, padx=(0, 8))
        self.entry.bind('<Return>', lambda _event: self._send())
        self.send_button = self._button(bottom, 'SEND', self._send)
        self.send_button.pack(side='right')
        self.entry.focus_set()

        self.chat = scrolledtext.ScrolledText(
            self.root, wrap='word', bg='#071019', fg='#d9f7ff', insertbackground='#53e7ff',
            selectbackground='#14445a', relief='flat', padx=18, pady=18,
            font=('Segoe UI', 11), spacing1=4, spacing3=8
        )
        self.chat.pack(side='top', fill='both', expand=True, padx=12, pady=(0, 8))
        self.chat.tag_configure('you', foreground='#6affb8', font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('jarvis', foreground='#53e7ff', font=('Segoe UI', 11, 'bold'))
        self.chat.tag_configure('system', foreground='#ffd166', font=('Segoe UI', 10, 'bold'))
        self.chat.tag_configure('body', foreground='#e6f5fa')
        self.chat.configure(state='disabled')

        self._append(
            'JARVIS',
            'OMEGA V5 online. Type a message, attach up to '
            f'{settings.max_image_attachments} images, or use Screen Vision. Mic input remains disabled.'
        )

    @staticmethod
    def _button(parent, text: str, command):
        return tk.Button(
            parent, text=text, command=command, bg='#103346', fg='#d8f9ff',
            activebackground='#19506d', activeforeground='white', relief='flat',
            cursor='hand2', padx=10, pady=6, font=('Segoe UI', 8, 'bold')
        )

    def _append(self, speaker: str, text: str) -> None:
        self.chat.configure(state='normal')
        tag = 'you' if speaker == 'YOU' else ('system' if speaker == 'SYSTEM' else 'jarvis')
        self.chat.insert('end', f'\n{speaker}\n', tag)
        self.chat.insert('end', f'{text}\n', 'body')
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def _set_busy(self, busy: bool, label: str = 'READY', color: str = '#66ffb2') -> None:
        self.busy = busy
        self.status.configure(text=label, fg=color)
        self.send_button.configure(state='disabled' if busy else 'normal')

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

    def _refresh_attachment_bar(self) -> None:
        self._preview_ref = None
        if not self.attached_images:
            self.preview_label.configure(
                image='', compound='left',
                text='No image attached • Ctrl+O to upload',
                fg='#8aa6b5'
            )
            return

        first = self.attached_images[0]
        names = ', '.join(path.name for path in self.attached_images[:3])
        if len(self.attached_images) > 3:
            names += f' +{len(self.attached_images) - 3} more'

        try:
            with Image.open(first) as image:
                preview = image.convert('RGB')
                preview.thumbnail((58, 42), Image.Resampling.LANCZOS)
                self._preview_ref = ImageTk.PhotoImage(preview)
            info = image_info(first)
            suffix = f' • first: {info["width"]}×{info["height"]}, {info["size_mb"]} MB'
            self.preview_label.configure(
                image=self._preview_ref, compound='left',
                text=f'  {len(self.attached_images)} image(s): {names}{suffix}',
                fg='#d9f7ff'
            )
        except Exception:
            self.preview_label.configure(
                image='', text=f'{len(self.attached_images)} image(s): {names}', fg='#d9f7ff'
            )

    def _upload_images(self) -> None:
        if self.busy:
            return
        selected = filedialog.askopenfilenames(
            title=f'Upload up to {settings.max_image_attachments} images',
            filetypes=[
                ('Supported images', '*.png *.jpg *.jpeg *.webp'),
                ('PNG', '*.png'),
                ('JPEG', '*.jpg *.jpeg'),
                ('WEBP', '*.webp'),
            ],
        )
        if not selected:
            return
        try:
            paths = normalize_image_paths(list(selected))
        except Exception as exc:
            messagebox.showerror('Image Upload', str(exc))
            return
        self.attached_images = paths
        self._refresh_attachment_bar()
        self._append('SYSTEM', 'Image attached. Type your question and press SEND, or press SEND with an empty prompt for general analysis.')
        self.entry.focus_set()

    def _paste_image(self) -> None:
        if self.busy:
            return
        try:
            path = save_clipboard_image()
            validate_image(path)
        except Exception as exc:
            messagebox.showerror('Paste Image', str(exc))
            return
        self.attached_images = [path]
        self._refresh_attachment_bar()
        self._append('SYSTEM', f'Clipboard image attached: {path.name}')
        self.entry.focus_set()

    def _clear_images(self) -> None:
        self.attached_images = []
        self._refresh_attachment_bar()

    def _image_help(self) -> None:
        messagebox.showinfo(
            'JARVIS V5 Image Upload',
            'IMAGE UPLOAD\n\n'
            '1. Click UPLOAD IMAGE or press Ctrl+O.\n'
            f'2. Select up to {settings.max_image_attachments} PNG/JPG/JPEG/WEBP images.\n'
            '3. Type what you want JARVIS to inspect and press SEND.\n'
            '4. You can also press SEND without text for general image analysis.\n'
            '5. PASTE IMAGE reads an image from your Windows clipboard.\n\n'
            f'Per-file limit: {settings.max_image_mb} MB.\n'
            f'Images are resized to about {settings.image_max_dimension}px max dimension before provider upload.\n'
            'Images are not uploaded to GitHub by this feature. They are sent to your configured AI provider for analysis.'
        )

    def _send(self) -> None:
        if self.busy:
            return
        text = self.entry.get().strip()
        images = list(self.attached_images)
        if not text and not images:
            return
        self.entry.delete(0, 'end')

        if images:
            prompt = text or 'Analyze the attached image(s) carefully and tell me the important details.'
            names = ', '.join(path.name for path in images)
            self._append('YOU', f'{prompt}\n[Attached: {names}]')
            self._set_busy(True, 'IMAGE AI...', '#d98cff')
        else:
            prompt = text
            self._append('YOU', prompt)
            self._set_busy(True, 'THINKING...', '#ffd166')

        threading.Thread(
            target=self._answer_worker, args=(prompt, images), daemon=True
        ).start()

    def _answer_worker(self, text: str, images: list[Path]) -> None:
        try:
            answer = self.jarvis.analyze_images(images, text) if images else self.jarvis.chat(text)
            self.root.after(0, lambda: self._answer_done(answer, None, bool(images)))
        except Exception as exc:
            self.root.after(0, lambda: self._answer_done('', str(exc), False))

    def _answer_done(self, answer: str, error: str | None, clear_images: bool) -> None:
        self._set_busy(False)
        if error:
            self._append('JARVIS', f'ERROR: {error}')
            return
        self._append('JARVIS', answer)
        self.voice.speak(answer)
        if clear_images:
            self._clear_images()

    def _screen_vision(self) -> None:
        if self.busy:
            return
        prompt = simpledialog.askstring(
            'Screen Vision',
            'What should JARVIS inspect on your screen?',
            initialvalue='Analyze my screen, identify any errors or important UI state, and tell me what to do next.'
        )
        if prompt is None:
            return
        if not messagebox.askyesno(
            'Screen Capture Permission',
            'Allow JARVIS to capture the current screen and send it to the configured AI provider for analysis?'
        ):
            return
        self._set_busy(True, f'VISION… ≤{int(settings.vision_timeout_seconds)}s', '#d98cff')
        threading.Thread(target=self._vision_worker, args=(prompt,), daemon=True).start()

    def _vision_worker(self, prompt: str) -> None:
        try:
            screenshot = capture_screen()
            answer = self.jarvis.analyze_image(screenshot, prompt)
            self.root.after(0, lambda: self._vision_done(answer, screenshot.name, None))
        except Exception as exc:
            self.root.after(0, lambda: self._vision_done('', '', str(exc)))

    def _vision_done(self, answer: str, name: str, error: str | None) -> None:
        self._set_busy(False)
        if error:
            self._append('JARVIS', f'SCREEN VISION ERROR: {error}')
            return
        self._append('JARVIS', f'[Screen: {name}]\n{answer}')
        self.voice.speak(answer)

    def _learn_file(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title='Add a safe text/code file to JARVIS knowledge',
            filetypes=[
                ('Text and code', '*.txt *.md *.py *.js *.ts *.json *.csv *.html *.css *.sql *.yaml *.yml *.toml'),
                ('All files', '*.*'),
            ],
        )
        if not path:
            return
        self._set_busy(True, 'LEARNING...', '#d98cff')
        threading.Thread(target=self._learn_worker, args=(path,), daemon=True).start()

    def _learn_worker(self, path: str) -> None:
        result = self.jarvis.tools.call('index_local_text_file', {'file_path': path})
        self.root.after(0, lambda: self._learn_done(result))

    def _learn_done(self, result: str) -> None:
        self._set_busy(False)
        self._append('SYSTEM', f'Knowledge import result:\n{result}')

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
        self._append('JARVIS', f'New V5 session started: {sid}')

    def _toggle_voice(self) -> None:
        speaking = self.voice.toggle()
        self.voice_button.configure(text='MUTE VOICE' if speaking else 'UNMUTE VOICE')
        if speaking:
            self.voice.test('hinglish')

    def _show_status(self) -> None:
        provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
        stats = self.jarvis.memory.stats()
        messagebox.showinfo(
            'OMEGA V5 Status',
            f'Version: {settings.app_version}\n'
            f'Provider: {provider}\nModel: {settings.model}\nLast model: {self.jarvis.last_model_used}\n'
            f'Last request: {self.jarvis.last_request_kind}\nTool mode: {self.jarvis.last_tool_mode}\n'
            f'Free web tools: {settings.enable_public_web_tools}\n'
            f'Image upload: True ({settings.max_image_attachments} max)\n'
            f'Screen vision: True\n'
            f'AI timeout: {settings.ai_timeout_seconds}s\nVision timeout: {settings.vision_timeout_seconds}s\n'
            f'Voice: {settings.voice_engine}, pitch {settings.edge_voice_pitch}\n'
            f'Sessions: {stats["sessions"]}\nMessages: {stats["messages"]}\n'
            f'Facts: {stats["facts"]}\nKnowledge docs: {stats["knowledge_docs"]}'
        )

    def _close(self) -> None:
        self.voice.stop()
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    JarvisDesktop(root)
    root.mainloop()
