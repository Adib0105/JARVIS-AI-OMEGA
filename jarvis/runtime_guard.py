from __future__ import annotations

import json
import os
import threading
from typing import Callable

from .config import settings
from .response_quality import (
    STABLE_FREE_TEXT_MODEL,
    clean_display_text,
    local_identity_answer,
    looks_garbled,
    preferred_text_model,
)


def install_runtime_guards() -> None:
    """Compatibility shim retained for old launchers.

    Response quality and model-selection behavior are now composed directly into
    ``jarvis.core.JarvisOmega``. This function intentionally performs no class
    mutation, making CLI/desktop behavior independent of startup call order.
    """
    return None


def _rebrand_widget_tree(widget) -> None:
    try:
        text = widget.cget('text')
        if isinstance(text, str):
            updated = text.replace('V6', settings.app_version).replace('V7.5', settings.app_version)
            if updated != text:
                widget.configure(text=updated)
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _rebrand_widget_tree(child)
    except Exception:
        pass


def _rebrand_chat_history(app) -> None:
    chat = getattr(app, 'chat', None)
    if chat is None:
        return
    try:
        previous_state = str(chat.cget('state'))
        chat.configure(state='normal')
        for legacy in ('V6', 'V7.5'):
            start = '1.0'
            while True:
                index = chat.search(legacy, start, stopindex='end')
                if not index:
                    break
                chat.delete(index, f'{index}+{len(legacy)}c')
                chat.insert(index, settings.app_version)
                start = f'{index}+{len(settings.app_version)}c'
        chat.configure(state=previous_state)
    except Exception:
        pass


def run_adaptive_gui() -> None:
    """Launch desktop, voice controls and Command Center through composition."""
    import importlib.util
    import sys
    import tkinter as tk

    from . import gui as gui_module
    from .security.approval_ui import ask_approval
    from .security.audit_ui import show_audit_viewer
    from .security.policy import ApprovalDecision
    from .ui_command_center_composed import show_command_center
    from .voice_ui import voice_desktop_class

    root = tk.Tk()
    screen_w = max(800, root.winfo_screenwidth())
    screen_h = max(600, root.winfo_screenheight())
    compact = screen_h <= 820 or screen_w <= 1400

    if compact:
        try:
            current_scale = float(root.tk.call('tk', 'scaling'))
            root.tk.call('tk', 'scaling', max(1.0, current_scale * 0.93))
        except Exception:
            pass

    base_desktop = voice_desktop_class(gui_module.JarvisDesktop, gui_module)

    class AdaptiveJarvisDesktop(base_desktop):
        def __init__(self, root_widget) -> None:
            super().__init__(root_widget)
            # Tk child widgets can consume Ctrl+O before the root binding sees it.
            # Bind the focused input/chat widgets directly and return "break" from
            # the handler so one keypress always opens exactly one picker.
            for widget in (self.root, self.entry, self.chat):
                widget.bind('<Control-o>', self._upload_shortcut)
                widget.bind('<Control-O>', self._upload_shortcut)

        @staticmethod
        def _button(parent, text: str, command: Callable, accent: str = gui_module.CYAN):
            if not compact:
                return base_desktop._button(parent, text, command, accent)
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg='#0b2a3a',
                fg=accent,
                activebackground='#12445b',
                activeforeground='white',
                relief='flat',
                cursor='hand2',
                padx=8,
                pady=4,
                font=('Segoe UI', 8, 'bold'),
                highlightthickness=1,
                highlightbackground='#123f51',
            )

        def _confirm_tool(self, tool: str, args: dict):
            event = threading.Event()
            result = {'decision': ApprovalDecision.DENY.value}

            def ask() -> None:
                try:
                    if isinstance(args, dict) and '__approval__' in args:
                        result['decision'] = ask_approval(self.root, tool, args)
                    else:
                        allowed = gui_module.messagebox.askyesno(
                            f'JARVIS {settings.app_version} // Permission Gate',
                            f'Allow this local action?\n\nTool: {tool}\n\nArguments:\n{args}\n\n'
                            'Only approve if this matches your request.',
                            parent=self.root,
                        )
                        result['decision'] = (
                            ApprovalDecision.ALLOW_ONCE.value if allowed else ApprovalDecision.DENY.value
                        )
                    if result['decision'] == ApprovalDecision.CANCEL_MISSION.value:
                        try:
                            self.jarvis.cancel_mission()
                        except Exception:
                            pass
                finally:
                    event.set()

            self.root.after(0, ask)
            active = getattr(self.jarvis, '_active_request', None)
            timeout = active.remaining() if active is not None else settings.ai_timeout_seconds
            if not event.wait(timeout=timeout):
                return ApprovalDecision.DENY.value
            return result['decision']

        def _build_right_panel(self, parent):
            super()._build_right_panel(parent)

            self._button(
                parent,
                'QUICK DIAGNOSE',
                self._quick_diagnose,
                gui_module.GREEN,
            ).pack(fill='x', padx=10, pady=(2, 1), before=self.status)
            self._button(
                parent,
                'COMMAND CENTER',
                lambda: show_command_center(self.root, self.jarvis),
                gui_module.CYAN,
            ).pack(fill='x', padx=10, pady=(2, 1), before=self.status)
            self._button(
                parent,
                'AUDIT VIEWER',
                lambda: show_audit_viewer(
                    self.root,
                    getattr(getattr(self.jarvis, 'tools', None), 'audit', None),
                ),
                gui_module.GOLD,
            ).pack(fill='x', padx=10, pady=(2, 1), before=self.status)

        def _upload_shortcut(self, _event=None):
            if self.busy:
                self.status.configure(text='● FINISH CURRENT TASK FIRST', fg=gui_module.GOLD)
                return 'break'
            self._upload_images()
            return 'break'

        def _upload_images(self) -> None:
            if self.busy:
                self.status.configure(text='● FINISH CURRENT TASK FIRST', fg=gui_module.GOLD)
                return
            selected = gui_module.filedialog.askopenfilenames(
                parent=self.root,
                title=f'JARVIS {settings.app_version} // Upload up to {settings.max_image_attachments} images',
                filetypes=[
                    ('Supported images', '*.png *.jpg *.jpeg *.webp'),
                    ('PNG', '*.png'), ('JPEG', '*.jpg *.jpeg'), ('WEBP', '*.webp'),
                ],
            )
            if not selected:
                return
            try:
                self.attached_images = gui_module.normalize_image_paths(list(selected))
                self._refresh_attachment_bar()
                self._append('SYSTEM', 'Image attachment loaded. Type a question and press SEND.')
                self.entry.focus_set()
            except Exception as exc:
                gui_module.messagebox.showerror('Image Upload', str(exc), parent=self.root)

        def _image_help(self) -> None:
            """Interactive image center instead of a passive help popup."""
            win = tk.Toplevel(self.root)
            win.title(f'JARVIS {settings.app_version} // IMAGE CENTER')
            win.configure(bg='#07131d')
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()

            tk.Label(
                win,
                text='IMAGE CENTER',
                bg='#07131d', fg=gui_module.CYAN,
                font=('Segoe UI', 14, 'bold'),
            ).pack(anchor='w', padx=18, pady=(16, 4))
            tk.Label(
                win,
                text=(
                    f'Attached now: {len(self.attached_images)}/{settings.max_image_attachments}\n'
                    'Upload PNG/JPG/JPEG/WEBP, paste from clipboard, or inspect the current screen.\n'
                    'After attaching an image, type your question and press SEND.'
                ),
                bg='#07131d', fg=gui_module.TEXT, justify='left',
                font=('Segoe UI', 9), wraplength=470,
            ).pack(anchor='w', padx=18, pady=(0, 12))

            buttons = tk.Frame(win, bg='#07131d')
            buttons.pack(fill='x', padx=18, pady=(0, 16))

            def launch(callback) -> None:
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
                self.root.after(25, callback)

            self._button(buttons, 'UPLOAD IMAGE', lambda: launch(self._upload_images), gui_module.MAGENTA).pack(fill='x', pady=3)
            self._button(buttons, 'PASTE IMAGE', lambda: launch(self._paste_image), gui_module.MAGENTA).pack(fill='x', pady=3)
            self._button(buttons, 'SCREEN VISION', lambda: launch(self._screen_vision), gui_module.CYAN).pack(fill='x', pady=3)
            self._button(buttons, 'CLOSE', win.destroy, gui_module.MUTED).pack(fill='x', pady=(8, 0))
            win.lift()
            win.focus_force()

        def _run_tool_async(self, name: str, args: dict, label: str) -> None:
            """Run local tools without ever leaving the desktop stuck in busy state."""
            self._set_busy(True, label, gui_module.GOLD, 'thinking')

            def worker() -> None:
                try:
                    result = self.jarvis.tools.call(name, args)
                except Exception as exc:
                    result = json.dumps(
                        {'ok': False, 'error': f'{type(exc).__name__}: {exc}'},
                        ensure_ascii=False,
                    )
                try:
                    self.root.after(0, lambda r=result: self._tool_done(name, r))
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True, name=f'jarvis-tool-{name}').start()

        def _tool_done(self, name: str, result: str) -> None:
            self._set_busy(False)
            try:
                payload = json.loads(result)
            except Exception:
                payload = None

            if isinstance(payload, dict) and name == 'index_document':
                if not payload.get('ok'):
                    self._append('SYSTEM', f"LEARN DOCUMENT FAILED: {payload.get('error', 'Unknown error')}")
                else:
                    body = payload.get('result') or {}
                    document = body.get('document') or {}
                    index = body.get('index') or {}
                    lines = [
                        f"Document learned: {document.get('type', 'document').upper()}",
                        f"Status: {index.get('status', 'indexed')}",
                        f"Extracted characters: {document.get('characters', 0)}",
                        f"Knowledge chunks: {index.get('chunks', 0)}",
                    ]
                    if document.get('credential_redactions'):
                        lines.append(
                            f"Security: {document.get('credential_redactions')} credential-like value(s) redacted before storage."
                        )
                    if document.get('warning'):
                        lines.append(f"Warning: {document['warning']}")
                    self._append('SYSTEM', '\n'.join(lines))
                self._refresh_tasks()
                return

            if isinstance(payload, dict) and name == 'run_project_tests':
                if not payload.get('ok'):
                    self._append('SYSTEM', f"CODE TESTS FAILED TO START: {payload.get('error', 'Unknown error')}")
                else:
                    body = payload.get('result') or {}
                    returncode = int(body.get('returncode', -1))
                    state = 'PASSED' if returncode == 0 else 'FAILED'
                    output = str(body.get('output') or '').strip()
                    interpreter = str(body.get('interpreter') or 'Python')
                    summary = f'CODE TESTS {state}\nInterpreter: {interpreter}'
                    if output:
                        summary += '\n\n' + output[-12000:]
                    self._append('SYSTEM', summary)
                self._refresh_tasks()
                return

            self._append('SYSTEM', f'{name}:\n{result}')
            self._refresh_tasks()

        def _quick_diagnose(self) -> None:
            if self.busy:
                return
            self._set_busy(True, 'DIAGNOSING', gui_module.GREEN, 'thinking')

            def worker() -> None:
                try:
                    dependencies = {
                        name: importlib.util.find_spec(name) is not None
                        for name in ('edge_tts', 'pyttsx3', 'PIL', 'sounddevice', 'speech_recognition', 'pyautogui')
                    }
                    metrics = gui_module.system_metrics()
                    lines = [
                        f"Runtime: {'PACKAGED EXE' if getattr(sys, 'frozen', False) else 'PYTHON SOURCE'}",
                        f'AI provider: {settings.provider} / {settings.model}',
                        f"Voice: {'READY' if dependencies['edge_tts'] else 'MISSING'} ({settings.voice_engine})",
                        f"Microphone packages: {'READY' if dependencies['sounddevice'] and dependencies['speech_recognition'] else 'MISSING'}",
                        f"Image support: {'READY' if dependencies['PIL'] else 'MISSING'}",
                        f"Desktop automation: {'READY' if dependencies['pyautogui'] else 'MISSING'}",
                    ]
                    if metrics.get('available') is not False:
                        lines.extend([
                            f"CPU: {metrics.get('cpu_percent', 0):.1f}%",
                            f"RAM: {metrics.get('memory_percent', 0):.1f}%",
                            f"Disk: {metrics.get('disk_percent', 0):.1f}%",
                        ])
                    lines.append('Physical microphone/speaker quality is NOT VERIFIED by this software check.')
                    message = '\n'.join(lines)
                except Exception as exc:
                    message = f'DIAGNOSTICS ERROR: {type(exc).__name__}: {exc}'
                self.root.after(0, lambda m=message: self._diagnose_done(m))

            threading.Thread(target=worker, daemon=True, name='jarvis-quick-diagnose').start()

        def _diagnose_done(self, message: str) -> None:
            self._set_busy(False)
            self._append('SYSTEM', 'QUICK DIAGNOSE\n' + message)

    app = AdaptiveJarvisDesktop(root)
    root.title(f'JARVIS AI OMEGA {settings.app_version} // RELIABLE ARC DESKTOP AGENT')
    _rebrand_widget_tree(root)
    _rebrand_chat_history(app)
    root.bind(
        '<Control-Shift-A>',
        lambda _event: show_audit_viewer(
            root,
            getattr(getattr(app.jarvis, 'tools', None), 'audit', None),
        ),
    )
    root.bind('<Control-Shift-C>', lambda _event: show_command_center(root, app.jarvis))

    if compact:
        root.minsize(min(1040, screen_w - 40), min(620, screen_h - 100))
    try:
        if os.name == 'nt':
            root.state('zoomed')
    except Exception:
        pass
    root.mainloop()


__all__ = [
    'STABLE_FREE_TEXT_MODEL',
    'clean_display_text',
    'install_runtime_guards',
    'local_identity_answer',
    'looks_garbled',
    'preferred_text_model',
    'run_adaptive_gui',
]
