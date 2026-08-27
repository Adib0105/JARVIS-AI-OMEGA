from __future__ import annotations

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
    """Launch the desktop through a subclass rather than mutating GUI classes."""
    import tkinter as tk

    from . import gui as gui_module
    from .security.approval_ui import ask_approval
    from .security.audit_ui import show_audit_viewer
    from .security.policy import ApprovalDecision
    from .ui_command_center import show_command_center

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

    base_desktop = gui_module.JarvisDesktop

    class AdaptiveJarvisDesktop(base_desktop):
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
