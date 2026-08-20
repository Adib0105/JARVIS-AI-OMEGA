from __future__ import annotations

import os
import threading
import tkinter as tk

from .voice_personality import speechify


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def install_voice_ui() -> None:
    """Install premium V7.5 voice controls and low-latency conversational turns."""
    from . import gui as gui_module
    from .config import settings
    from .microphone import record_until_silence

    desktop = gui_module.JarvisDesktop
    if getattr(desktop, '_v75_voice_ui_installed', False):
        return

    original_init = desktop.__init__
    original_input = desktop._build_input_bar
    original_voice_state = desktop._voice_state_changed
    original_toggle_voice = desktop._toggle_voice
    original_push_to_talk = desktop._push_to_talk

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
        if hasattr(self, 'live_voice_button'):
            enabled = bool(getattr(self, '_live_voice_enabled', False))
            self.live_voice_button.configure(
                text='LIVE: ON' if enabled else 'LIVE: OFF',
                fg=gui_module.MAGENTA if enabled else gui_module.GREEN,
            )

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

    def start_vad_turn(self, *, interrupt: bool = False) -> None:
        if getattr(self, 'busy', False) or getattr(self, '_live_listening', False):
            return
        if not settings.enable_mic_input:
            return
        if interrupt:
            self.voice.stop()
        self._live_listening = True
        self._set_busy(True, 'LISTENING', gui_module.MAGENTA, 'listening')

        def worker() -> None:
            try:
                text = record_until_silence(
                    language=settings.speech_language,
                    max_seconds=float(os.getenv('VOICE_MAX_UTTERANCE_SECONDS', '15')),
                    start_timeout=float(os.getenv('VOICE_START_TIMEOUT_SECONDS', '5')),
                    silence_seconds=float(os.getenv('VOICE_SILENCE_SECONDS', '0.75')),
                    speech_threshold=float(os.getenv('VOICE_VAD_THRESHOLD', '420')),
                    on_speech_start=self.voice.stop,
                )
                self.root.after(0, lambda value=text: vad_done(self, value, None))
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda value=message: vad_done(self, '', value))

        threading.Thread(target=worker, daemon=True, name='jarvis-live-vad').start()

    def vad_done(self, text: str, error: str | None) -> None:
        self._live_listening = False
        self._set_busy(False)
        if error:
            self._append('SYSTEM', f'MIC: {error}')
            return
        if not text:
            if getattr(self, '_live_voice_enabled', False):
                self.status.configure(text='● LIVE READY', fg=gui_module.GREEN)
            return
        self.entry.delete(0, 'end')
        self.entry.insert(0, text)
        self._send_text(text, from_voice=True)

    def toggle_live(self) -> None:
        self._live_voice_enabled = not bool(getattr(self, '_live_voice_enabled', False))
        update_voice_panel(self)
        if self._live_voice_enabled:
            self._append('SYSTEM', 'Live conversation enabled. JARVIS will listen after each spoken reply. Ctrl+M interrupts speech immediately.')
            if self.voice.state == 'idle' and not self.busy:
                self.root.after(150, lambda: start_vad_turn(self))
        else:
            self._append('SYSTEM', 'Live conversation disabled.')

    def v75_init(self, root) -> None:
        original_init(self, root)
        self._live_voice_enabled = _env_bool('ENABLE_LIVE_CONVERSATION', False)
        self._live_listening = False

        raw_speak = self.voice.speak

        def premium_speak(text: str) -> None:
            spoken = speechify(text)
            if spoken:
                raw_speak(spoken)

        self.voice.speak = premium_speak
        root.bind('<Escape>', lambda _event: voice_stop(self))
        root.bind('<Control-space>', lambda _event: voice_play_pause(self))
        root.bind('<Control-minus>', lambda _event: voice_slower(self))
        root.bind('<Control-equal>', lambda _event: voice_faster(self))
        root.bind('<Control-plus>', lambda _event: voice_faster(self))
        root.bind('<Control-Shift-v>', lambda _event: toggle_live(self))
        update_voice_panel(self)
        if self._live_voice_enabled and settings.enable_mic_input:
            root.after(800, lambda: start_vad_turn(self))

    def v75_input_bar(self) -> None:
        original_input(self)
        strip = tk.Frame(
            self.root, bg='#061725', padx=14, pady=4,
            highlightbackground=gui_module.CYAN_DIM, highlightthickness=1,
        )
        strip.pack(side='bottom', fill='x')
        self.voice_player_status = tk.StringVar(value='VOICE: IDLE')
        tk.Label(
            strip, textvariable=self.voice_player_status, bg='#061725', fg=gui_module.GREEN,
            font=('Consolas', 8, 'bold'),
        ).pack(side='left', padx=(0, 8))
        self._button(strip, '− SPEED', lambda: voice_slower(self), gui_module.CYAN).pack(side='left', padx=(0, 3))
        self.voice_play_button = self._button(strip, 'PLAY / PAUSE', lambda: voice_play_pause(self), gui_module.GREEN)
        self.voice_play_button.pack(side='left', padx=3)
        self._button(strip, 'STOP', lambda: voice_stop(self), gui_module.RED).pack(side='left', padx=3)
        self._button(strip, 'SPEED +', lambda: voice_faster(self), gui_module.CYAN).pack(side='left', padx=3)
        self.voice_speed_label = tk.Label(
            strip, text=self.voice.speed_label, bg='#0b2a3a', fg=gui_module.GOLD,
            padx=10, pady=5, font=('Consolas', 9, 'bold'), cursor='hand2',
        )
        self.voice_speed_label.pack(side='left', padx=(5, 5))
        self.voice_speed_label.bind('<Button-1>', lambda _event: voice_reset_speed(self))
        self.live_voice_button = self._button(strip, 'LIVE: OFF', lambda: toggle_live(self), gui_module.GREEN)
        self.live_voice_button.pack(side='left', padx=(3, 8))
        tk.Label(
            strip,
            text='Ctrl+M Barge-in  •  Esc Stop  •  Ctrl+Space Pause  •  Ctrl+Shift+V Live',
            bg='#061725', fg=gui_module.MUTED, font=('Segoe UI', 7),
        ).pack(side='right')

    def v75_voice_state_changed(self, state: str) -> None:
        original_voice_state(self, state)
        try:
            self.root.after(0, lambda s=state: update_voice_panel(self, s))
            if state == 'idle' and getattr(self, '_live_voice_enabled', False):
                self.root.after(220, lambda: start_vad_turn(self))
        except Exception:
            pass

    def v75_push_to_talk(self) -> None:
        if self.voice.state in {'speaking', 'paused'}:
            start_vad_turn(self, interrupt=True)
            return
        if _env_bool('VOICE_USE_VAD', True):
            start_vad_turn(self)
            return
        original_push_to_talk(self)

    def v75_toggle_voice(self) -> None:
        original_toggle_voice(self)
        update_voice_panel(self)

    def v75_close(self) -> None:
        self._live_voice_enabled = False
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

    desktop.__init__ = v75_init
    desktop._build_input_bar = v75_input_bar
    desktop._voice_state_changed = v75_voice_state_changed
    desktop._push_to_talk = v75_push_to_talk
    desktop._toggle_voice = v75_toggle_voice
    desktop._close = v75_close
    desktop._v7_voice_ui_installed = True
    desktop._v75_voice_ui_installed = True
