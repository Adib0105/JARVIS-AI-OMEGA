from __future__ import annotations

import tkinter as tk


def install_voice_ui() -> None:
    """Install compact V7 media-style controls onto the existing desktop GUI."""
    from . import gui as gui_module

    desktop = gui_module.JarvisDesktop
    if getattr(desktop, '_v7_voice_ui_installed', False):
        return

    original_init = desktop.__init__
    original_right = desktop._build_right_panel
    original_voice_state = desktop._voice_state_changed
    original_toggle_voice = desktop._toggle_voice

    def update_voice_panel(self, state: str | None = None) -> None:
        voice = getattr(self, 'voice', None)
        if voice is None:
            return
        current = (state or voice.state or 'idle').upper()
        if hasattr(self, 'voice_player_status'):
            self.voice_player_status.set(f'VOICE: {current}  //  {voice.speed_label}')
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
        update_voice_panel(self)

    def v7_right_panel(self, parent) -> None:
        original_right(self, parent)

        player = tk.Frame(
            parent,
            bg=gui_module.PANEL_2,
            padx=7,
            pady=6,
            highlightbackground=gui_module.CYAN_DIM,
            highlightthickness=1,
        )
        player.pack(fill='x', padx=10, pady=(4, 2), before=self.status)

        top = tk.Frame(player, bg=gui_module.PANEL_2)
        top.pack(fill='x', pady=(0, 4))
        self.voice_player_status = tk.StringVar(value=f'VOICE: IDLE  //  {self.voice.speed_label}')
        tk.Label(
            top,
            textvariable=self.voice_player_status,
            bg=gui_module.PANEL_2,
            fg=gui_module.GREEN,
            font=('Consolas', 8, 'bold'),
        ).pack(side='left')
        self.voice_speed_label = tk.Label(
            top,
            text=self.voice.speed_label,
            bg=gui_module.PANEL_2,
            fg=gui_module.GOLD,
            font=('Consolas', 8, 'bold'),
            cursor='hand2',
        )
        self.voice_speed_label.pack(side='right')
        self.voice_speed_label.bind('<Button-1>', lambda _event: voice_reset_speed(self))

        controls = tk.Frame(player, bg=gui_module.PANEL_2)
        controls.pack(fill='x')
        self._button(controls, '− SPEED', lambda: voice_slower(self), gui_module.CYAN).pack(
            side='left', fill='x', expand=True, padx=(0, 2)
        )
        self.voice_play_button = self._button(
            controls, 'PLAY / PAUSE', lambda: voice_play_pause(self), gui_module.GREEN
        )
        self.voice_play_button.pack(side='left', fill='x', expand=True, padx=2)
        self._button(controls, 'STOP', lambda: voice_stop(self), gui_module.RED).pack(
            side='left', fill='x', expand=True, padx=2
        )
        self._button(controls, 'SPEED +', lambda: voice_faster(self), gui_module.CYAN).pack(
            side='left', fill='x', expand=True, padx=(2, 0)
        )

        tk.Label(
            player,
            text='Esc Stop  •  Ctrl+Space Play/Pause  •  Ctrl− / Ctrl+ Speed',
            bg=gui_module.PANEL_2,
            fg=gui_module.MUTED,
            font=('Segoe UI', 7),
        ).pack(anchor='w', pady=(4, 0))

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
        # Important: shutdown kills the active edge_playback process tree before
        # destroying Tk, so speech cannot outlive the desktop app.
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
    desktop._build_right_panel = v7_right_panel
    desktop._voice_state_changed = v7_voice_state_changed
    desktop._toggle_voice = v7_toggle_voice
    desktop._close = v7_close
    desktop._v7_voice_ui_installed = True
