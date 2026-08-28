from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
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


def _read_test_output_tail(path: Path | None, max_bytes: int = 65536, max_chars: int = 12000) -> str:
    """Read only the tail of a test log so very noisy suites cannot pressure the GUI."""
    if path is None or not path.is_file():
        return ''
    try:
        with path.open('rb') as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max(4096, int(max_bytes))), os.SEEK_SET)
            data = handle.read(max(4096, int(max_bytes)))
        return data.decode('utf-8', errors='replace')[-max(1000, int(max_chars)):].strip()
    except Exception as exc:
        return f'[Could not read test log: {type(exc).__name__}: {exc}]'


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
            self._test_process: subprocess.Popen | None = None
            self._test_output_handle = None
            self._test_output_path: Path | None = None
            self._test_started_at = 0.0
            self._test_timeout = 0
            self._test_interpreter = ''
            self._test_stop_reason = ''
            self._test_stop_requested_at = 0.0
            self._test_auth_queue: queue.Queue = queue.Queue(maxsize=1)

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

        def _code_tests(self) -> None:
            """Run tests fully outside the Tk/UI process and poll them without blocking."""
            if self.busy:
                return
            folder = gui_module.filedialog.askdirectory(
                parent=self.root,
                title='Select approved Python project folder with tests/',
            )
            if not folder:
                return

            args = {'project_dir': folder, 'timeout': 180}
            self._set_busy(True, 'AUTHORIZING TESTS', gui_module.GOLD, 'thinking')
            self._test_auth_queue = queue.Queue(maxsize=1)

            def authorize() -> None:
                try:
                    outcome = self.jarvis.tools.permissions.check('run_project_tests', args)
                    item = (bool(outcome.allowed), str(outcome.reason))
                except Exception as exc:
                    item = (False, f'{type(exc).__name__}: {exc}')
                try:
                    self._test_auth_queue.put_nowait(item)
                except queue.Full:
                    pass

            threading.Thread(target=authorize, daemon=True, name='jarvis-test-authorize').start()
            self.root.after(60, lambda: self._poll_test_authorization(folder, 180))

        def _poll_test_authorization(self, folder: str, timeout: int) -> None:
            try:
                allowed, reason = self._test_auth_queue.get_nowait()
            except queue.Empty:
                if self.busy and self._test_process is None:
                    self.root.after(60, lambda: self._poll_test_authorization(folder, timeout))
                return

            if not allowed:
                self._set_busy(False)
                self._append('SYSTEM', f'CODE TESTS NOT STARTED: {reason}')
                return
            self._launch_code_test_process(folder, timeout)

        def _launch_code_test_process(self, folder: str, timeout: int) -> None:
            output_handle = None
            output_path: Path | None = None
            try:
                spec = self.jarvis.tools.coding.prepare_unit_tests(folder, timeout)
                output_handle = tempfile.NamedTemporaryFile(
                    mode='w+b', prefix='jarvis-code-tests-', suffix='.log', delete=False
                )
                output_path = Path(output_handle.name)
                env = os.environ.copy()
                env['PYTHONUNBUFFERED'] = '1'
                env['PYTHONIOENCODING'] = 'utf-8'

                creationflags = 0
                if os.name == 'nt':
                    creationflags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                    creationflags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                    # Heavy suites must never starve the desktop event loop.
                    creationflags |= getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)

                process = subprocess.Popen(
                    spec['command'],
                    cwd=spec['cwd'],
                    stdin=subprocess.DEVNULL,
                    stdout=output_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    env=env,
                    creationflags=creationflags,
                    start_new_session=(os.name != 'nt'),
                )
            except Exception as exc:
                try:
                    if output_handle is not None:
                        output_handle.close()
                except Exception:
                    pass
                try:
                    if output_path is not None:
                        output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                self._set_busy(False)
                self._append('SYSTEM', f'CODE TESTS FAILED TO START: {type(exc).__name__}: {exc}')
                return

            self._test_process = process
            self._test_output_handle = output_handle
            self._test_output_path = output_path
            self._test_started_at = time.monotonic()
            self._test_timeout = int(spec['timeout'])
            self._test_interpreter = str(spec['interpreter'])
            self._test_stop_reason = ''
            self._test_stop_requested_at = 0.0
            self.status.configure(text='● TESTING 0s', fg=gui_module.GOLD)
            self.root.after(120, self._poll_code_test_process)

        def _poll_code_test_process(self) -> None:
            process = self._test_process
            if process is None:
                return

            returncode = process.poll()
            elapsed = max(0.0, time.monotonic() - self._test_started_at)
            if returncode is None:
                if not self._test_stop_reason and elapsed >= float(self._test_timeout):
                    self._request_code_test_stop('TIMED OUT')
                elif self._test_stop_reason and self._test_stop_requested_at:
                    if time.monotonic() - self._test_stop_requested_at >= 2.5:
                        try:
                            process.kill()
                        except Exception:
                            pass

                if self._test_stop_reason:
                    label = f'{self._test_stop_reason} - STOPPING'
                    color = gui_module.RED
                else:
                    label = f'TESTING {int(elapsed)}s / {self._test_timeout}s'
                    color = gui_module.GOLD
                self.status.configure(text=f'● {label}', fg=color)
                self.root.after(180, self._poll_code_test_process)
                return

            self._finish_code_test_process(int(returncode))

        def _request_code_test_stop(self, reason: str) -> None:
            process = self._test_process
            if process is None or process.poll() is not None:
                return
            if not self._test_stop_reason:
                self._test_stop_reason = str(reason or 'CANCELLED')
                self._test_stop_requested_at = time.monotonic()

            stopped = False
            if os.name == 'nt':
                try:
                    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                    subprocess.Popen(
                        ['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        shell=False,
                        creationflags=flags,
                    )
                    stopped = True
                except Exception:
                    stopped = False
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    stopped = True
                except Exception:
                    stopped = False
            if not stopped:
                try:
                    process.terminate()
                except Exception:
                    pass

        def _finish_code_test_process(self, returncode: int) -> None:
            try:
                if self._test_output_handle is not None:
                    self._test_output_handle.flush()
                    self._test_output_handle.close()
            except Exception:
                pass

            output = _read_test_output_tail(self._test_output_path)
            stop_reason = self._test_stop_reason
            interpreter = self._test_interpreter or 'Python'
            elapsed = max(0.0, time.monotonic() - self._test_started_at)

            try:
                if self._test_output_path is not None:
                    self._test_output_path.unlink(missing_ok=True)
            except Exception:
                pass

            self._test_process = None
            self._test_output_handle = None
            self._test_output_path = None
            self._test_started_at = 0.0
            self._test_timeout = 0
            self._test_interpreter = ''
            self._test_stop_reason = ''
            self._test_stop_requested_at = 0.0
            self._set_busy(False)

            if stop_reason == 'TIMED OUT':
                summary = f'CODE TESTS TIMED OUT after {elapsed:.1f}s\nInterpreter: {interpreter}'
            elif stop_reason:
                summary = f'CODE TESTS {stop_reason}\nInterpreter: {interpreter}'
            else:
                state = 'PASSED' if int(returncode) == 0 else 'FAILED'
                summary = f'CODE TESTS {state} in {elapsed:.1f}s\nInterpreter: {interpreter}'
            if output:
                summary += '\n\n' + output
            self._append('SYSTEM', summary)
            self._refresh_tasks()

        def _cancel_request(self) -> None:
            process = self._test_process
            if process is not None and process.poll() is None:
                self._request_code_test_stop('CANCELLED')
                self.status.configure(text='● CANCELLING CODE TESTS', fg=gui_module.RED)
                return
            super()._cancel_request()

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

        def _close(self) -> None:
            process = self._test_process
            if process is not None and process.poll() is None:
                self._request_code_test_stop('APP CLOSING')
            super()._close()

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
