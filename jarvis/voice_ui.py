from __future__ import annotations

import tkinter as tk


def voice_desktop_class(base_cls, gui_module):
    """Return a desktop subclass with media-style emotional voice controls composed in."""

    class VoiceEnabledDesktop(base_cls):
        def _update_voice_panel(self, state: str | None = None) -> None:
            voice = getattr(self, 'voice', None)
            if voice is None:
                return
            current = (state or voice.state or 'idle').upper()
            emotion = str(getattr(voice, 'emotion', '') or '').strip().upper()
            detail = f' • {emotion}' if current in {'SPEAKING', 'PAUSED'} and emotion else ''
            if hasattr(self, 'voice_player_status'):
                self.voice_player_status.set(f'VOICE: {current}{detail}')
            if hasattr(self, 'voice_play_button'):
                self.voice_play_button.configure(text='RESUME' if voice.paused else 'PLAY / PAUSE')
            if hasattr(self, 'voice_speed_label'):
                self.voice_speed_label.configure(text=voice.speed_label)

        def _voice_play_pause(self) -> None:
            state = self.voice.toggle_pause()
            self._update_voice_panel('paused' if state == 'paused' else self.voice.state)

        def _voice_stop(self) -> None:
            self.voice.stop()
            self._update_voice_panel('idle')

        def _voice_slower(self) -> None:
            self.voice.speed_down()
            self._update_voice_panel()

        def _voice_faster(self) -> None:
            self.voice.speed_up()
            self._update_voice_panel()

        def _voice_reset_speed(self) -> None:
            self.voice.reset_speed()
            self._update_voice_panel()

        def __init__(self, root) -> None:
            super().__init__(root)
            # Wake acknowledgement is profile-aware; creator identity remains a
            # separate immutable product fact in the system prompt.
            try:
                self.wake_listener.on_wake = lambda: self.voice.speak(
                    f'Hello {gui_module.settings.user_name}, main sun rahi hoon.'
                )
            except Exception:
                pass
            root.bind('<Escape>', lambda _event: self._voice_stop())
            root.bind('<Control-space>', lambda _event: self._voice_play_pause())
            root.bind('<Control-minus>', lambda _event: self._voice_slower())
            root.bind('<Control-equal>', lambda _event: self._voice_faster())
            root.bind('<Control-plus>', lambda _event: self._voice_faster())
            self._update_voice_panel()

        def _build_input_bar(self) -> None:
            super()._build_input_bar()
            strip = tk.Frame(self.root, bg='#061725', padx=14, pady=4, highlightbackground=gui_module.CYAN_DIM, highlightthickness=1)
            strip.pack(side='bottom', fill='x')
            self.voice_player_status = tk.StringVar(value='VOICE: IDLE')
            tk.Label(strip, textvariable=self.voice_player_status, bg='#061725', fg=gui_module.GREEN, font=('Consolas', 8, 'bold')).pack(side='left', padx=(0, 8))
            self._button(strip, '− SPEED', self._voice_slower, gui_module.CYAN).pack(side='left', padx=(0, 3))
            self.voice_play_button = self._button(strip, 'PLAY / PAUSE', self._voice_play_pause, gui_module.GREEN); self.voice_play_button.pack(side='left', padx=3)
            self._button(strip, 'STOP', self._voice_stop, gui_module.RED).pack(side='left', padx=3)
            self._button(strip, 'SPEED +', self._voice_faster, gui_module.CYAN).pack(side='left', padx=3)
            self.voice_speed_label = tk.Label(strip, text=self.voice.speed_label, bg='#0b2a3a', fg=gui_module.GOLD, padx=10, pady=5, font=('Consolas', 9, 'bold'), cursor='hand2')
            self.voice_speed_label.pack(side='left', padx=(5, 10)); self.voice_speed_label.bind('<Button-1>', lambda _event: self._voice_reset_speed())
            tk.Label(strip, text='Esc Stop   •   Ctrl+Space Play/Pause   •   Ctrl− / Ctrl+ Speed', bg='#061725', fg=gui_module.MUTED, font=('Segoe UI', 7)).pack(side='right')

        def _voice_state_changed(self, state: str) -> None:
            super()._voice_state_changed(state)
            try:
                self.root.after(0, lambda s=state: self._update_voice_panel(s))
                if state == 'error':
                    self.root.after(0, lambda: self._append('SYSTEM', 'VOICE ERROR: speech synthesis/playback failed. Text response is still available; check Windows audio output/network and retry VOICE TEST.'))
            except Exception:
                pass

        def _toggle_voice(self) -> None:
            super()._toggle_voice(); self._update_voice_panel()

        def _close(self) -> None:
            try: self.wake_listener.stop()
            except Exception: pass
            try: self.voice.shutdown(wait=True)
            except Exception: pass
            try:
                if self.hud: self.hud.stop()
            except Exception: pass
            self.root.destroy()

    VoiceEnabledDesktop.__name__ = f'VoiceEnabled{base_cls.__name__}'
    return VoiceEnabledDesktop


def install_voice_ui() -> None:
    return None


__all__ = ['install_voice_ui', 'voice_desktop_class']
