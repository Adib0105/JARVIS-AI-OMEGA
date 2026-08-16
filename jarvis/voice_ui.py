from __future__ import annotations

import tkinter as tk


def install_voice_ui() -> None:
    """Install always-visible V7 media-style speech controls onto the desktop GUI."""
    from . import gui as gui_module

    desktop = gui_module.JarvisDesktop
    if getattr(desktop, '_v7_voice_ui_installed', False):
        return

    original_init = desktop.__init__
    original_input = desktop._build_input_bar
    original_voice_state = desktop._voice_state_changed
    original_toggle_voice = desktop._toggle_voice

    def update_voice_panel(self, state: str | None = None) -> None:
        voice = getattr(self, 'voice', None)
        if voice is None:
            return
        current = (state or voice.state or 'idle').upper()
        if hasattr(self, 'voice_player_status'):
            self.voice_player_status.set(f'VOICE: {current}')
        if hasattr(self, 'voice_play_button'):
            self.voice_play_button.configure(text='RESUME' if voice.paused else 'PLAY / PAUSE')
        if hasattr(self, 'voice_speed_label'):
            self.voice_speed_label.configure(text=voice.speed_label)

    def voice_play_pause(self) -> None:
        state = self.voice.toggle_pause()
        update_voice_panel(self, 'paused' if state == 'paused' else self.voice.state)

    def voice_stop(self) -> None:
        self.voice.stop()
        update_voice_panel(self, 'idle')

    def voice_slower(self) -> None:
        self.voice.speed_down()
        update_voice_panel(self)

    def voice_faster(self) -> None:
        self.voice.speed_up()
        update_voice_panel(self)

    def voice_reset_speed(self) -> None:
        self.voice.reset_speed()
        update_voice_panel(self)

    def v7_init(self, root) -> None:
        original_init(self, root)
        # Media shortcuts stay independent from chat/mission execution.
        root.bind('<Escape>', lambda _event: voice_stop(self))
        root.bind('<Control-space>', lambda _event: voice_play_pause(self))
        root.bind('<Control-minus>', lambda _event: voice_slower(self))
        root.bind('<Control-equal>', lambda _event: voice_faster(self))
        root.bind('<Control-plus>', lambda _event: voice_faster(self))
        update_voice_panel(self)

    def v7_input_bar(self) -> None:
        # Build the normal chat input first. A second bottom-packed strip is then
        # placed immediately above it, so controls remain visible even on 768p.
        original_input(self)

        strip = tk.Frame(
            self.root,
            bg='#061725',
            padx=14,
            pady=4,
            highlightbackground=gui_module.CYAN_DIM,
            highlightthickness=1,
        )
        strip.pack(side='bottom', fill='x')

        self.voice_player_status = tk.StringVar(value='VOICE: IDLE')
        tk.Label(
            strip,
            textvariable=self.voice_player_status,
            bg='#061725',
            fg=gui_module.GREEN,
            font=('Consolas', 8, 'bold'),
        ).pack(side='left', padx=(0, 8))

        self._button(strip, '− SPEED', lambda: voice_slower(self), gui_module.CYAN).pack(
            side='left', padx=(0, 3)
        )
        self.voice_play_button = self._button(
            strip, 'PLAY / PAUSE', lambda: voice_play_pause(self), gui_module.GREEN
        )
        self.voice_play_button.pack(side='left', padx=3)
        self._button(strip, 'STOP', lambda: voice_stop(self), gui_module.RED).pack(
            side='left', padx=3
        )
        self._button(strip, 'SPEED +', lambda: voice_faster(self), gui_module.CYAN).pack(
            side='left', padx=3
        )

        self.voice_speed_label = tk.Label(
            strip,
            text=self.voice.speed_label,
            bg='#0b2a3a',
            fg=gui_module.GOLD,
            padx=10,
            pady=5,
            font=('Consolas', 9, 'bold'),
            cursor='hand2',
        )
        self.voice_speed_label.pack(side='left', padx=(5, 10))
        self.voice_speed_label.bind('<Button-1>', lambda _event: voice_reset_speed(self))

        tk.Label(
            strip,
            text='Esc Stop   •   Ctrl+Space Play/Pause   •   Ctrl− / Ctrl+ Speed',
            bg='#061725',
            fg=gui_module.MUTED,
            font=('Segoe UI', 7),
        ).pack(side='right')

    def v7_voice_state_changed(self, state: str) -> None:
        original_voice_state(self, state)
        try:
            self.root.after(0, lambda s=state: update_voice_panel(self, s))
        except Exception:
            pass

    def v7_toggle_voice(self) -> None:
        original_toggle_voice(self)
        update_voice_panel(self)

    def v7_close(self) -> None:
        # shutdown() kills active edge_playback before Tk is destroyed, so speech
        # cannot continue after the desktop window has been closed.
        try:
            self.wake_listener.stop()
        except Exception:
            pass
        try:
            self.voice.shutdown(wait=True)
        except Exception:
            pass
        try:
            if self.hud:
                self.hud.stop()
        except Exception:
            pass
        self.root.destroy()

    desktop.__init__ = v7_init
    desktop._build_input_bar = v7_input_bar
    desktop._voice_state_changed = v7_voice_state_changed
    desktop._toggle_voice = v7_toggle_voice
    desktop._close = v7_close
    desktop._v7_voice_ui_installed = True
