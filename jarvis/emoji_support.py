from __future__ import annotations

import tkinter as tk

from .emoji_ui import emoji_font, show_emoji_picker


def install_emoji_support() -> None:
    """Add native emoji rendering and an in-app picker to the desktop UI.

    This is intentionally idempotent because packaged startup/diagnostics can import
    desktop modules more than once. We use the OS Unicode emoji font rather than
    shipping third-party artwork, so messages remain normal Unicode and work when
    pasted into WhatsApp, browsers, documents, and other apps.
    """
    from . import gui

    cls = gui.JarvisDesktop
    if getattr(cls, '_jarvis_emoji_support_installed', False):
        return

    original_input_bar = cls._build_input_bar
    original_center = cls._build_center

    def build_input_bar(self) -> None:
        original_input_bar(self)
        try:
            self.entry.configure(font=emoji_font(self.root, 12))
        except Exception:
            pass

        def open_picker(_event=None):
            show_emoji_picker(self.root, self.entry)
            return 'break'

        self._open_emoji_picker = open_picker
        try:
            self.entry.bind('<Control-Shift-e>', open_picker)
            self.entry.bind('<Control-Shift-E>', open_picker)
            self.root.bind('<Control-Shift-e>', open_picker)
            self.root.bind('<Control-Shift-E>', open_picker)
        except Exception:
            pass

        try:
            button = self._button(self.entry.master, '😀 EMOJI', open_picker, gui.GOLD)
            button.pack(side='right', padx=(4, 0))
            self.emoji_button = button
        except Exception:
            pass

    def build_center(self, parent: tk.Frame) -> None:
        original_center(self, parent)
        try:
            # Keep speaker headings in their existing fonts; body text uses an
            # emoji-capable Unicode font so emoji survive/render in chat history.
            self.chat.tag_configure('body', foreground=gui.TEXT, font=emoji_font(self.root, 11))
        except Exception:
            pass

    cls._build_input_bar = build_input_bar
    cls._build_center = build_center
    cls._jarvis_emoji_support_installed = True


__all__ = ['install_emoji_support']
