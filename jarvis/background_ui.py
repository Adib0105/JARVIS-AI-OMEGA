"""Windows tray lifecycle and background voice controls."""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .config import settings
from .daily_briefing import find_locations, valid_location
from .wake_service import BackgroundWakeListener


def preference_path():
    return settings.db_path.parent / 'background-settings.json'


def load_preferences():
    try:
        data = json.loads(preference_path().read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        clean = {'enabled': data.get('enabled') is True}
        if 'wake_weather' in data:
            clean['wake_weather'] = data.get('wake_weather') is True
        if 'fast_ack' in data:
            clean['fast_ack'] = data.get('fast_ack') is not False
        if 'auto_updates' in data:
            clean['auto_updates'] = data.get('auto_updates') is True
        if 'show_on_wake' in data:
            clean['show_on_wake'] = data.get('show_on_wake') is True
        if 'listen_after_wake' in data:
            clean['listen_after_wake'] = data.get('listen_after_wake') is not False
        if isinstance(data.get('model_path'), str):
            clean['model_path'] = data['model_path']
        if valid_location(data.get('location')):
            clean['location'] = data['location']
        return clean
    except (OSError, ValueError, UnicodeError):
        return {}


def save_preferences(data):
    path = preference_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def _wait_until_voice_finishes(voice, stop_event, *, start_timeout=1.5, finish_timeout=20.0):
    """Wait for queued acknowledgement speech without ever waiting forever.

    Voice synthesis is asynchronous and can legitimately remain ``idle`` for a
    short time while its worker dequeues the text.  A muted/disabled voice never
    becomes active, so the short start timeout lets command capture continue.
    """
    from .voice import VoiceOutput
    if isinstance(voice, VoiceOutput):
        return voice.wait_idle(stop_event, timeout=finish_timeout)
    if not getattr(voice, 'enabled', False) or getattr(voice, 'muted', False):
        return True
    started = time.monotonic()
    active = False
    while not stop_event.is_set():
        state = getattr(voice, 'state', 'idle')
        if state != 'idle':
            active = True
        elif active:
            return True
        now = time.monotonic()
        if not active and now - started >= start_timeout:
            return True
        if now - started >= finish_timeout:
            return False
        stop_event.wait(0.05)
    return False


class BackgroundController:
    def __init__(self, desktop):
        self.desktop = desktop
        self.events = queue.Queue()
        self.preferences = load_preferences()
        self.enabled = False
        self.pending = False
        self.suppress_until = 0.0
        self.generation = 0
        self.retry_failures = 0
        self.retry_after_id = None
        self.followup_stop = threading.Event()
        self.followup_thread = None
        self.tray = None
        self.weather_snapshot = None
        self.weather_refreshing = False
        self.weather_next_refresh = 0.0
        self.last_wake_latency_ms = None
        self.heard_at = 0.0
        from .wake_model import MODEL_NAME, model_valid
        installed_model = settings.db_path.parent / 'models' / MODEL_NAME
        selected_model = self.preferences.get('model_path') or settings.vosk_model_path
        if not selected_model and model_valid(installed_model):
            selected_model = str(installed_model)
        self.listener = BackgroundWakeListener(selected_model, self.heard,
            lambda error: self.events.put(('error', error, self.generation)), self.suspended, settings.wake_word)
        desktop.root.after(100, self.poll)
        if self.preferences.get('enabled'):
            desktop.root.after(1000, lambda: self.enable(show_error=False, persist_choice=False))

    def suspended(self):
        d = self.desktop
        return not self.enabled or self.pending or d.busy or d.voice.state != 'idle' or time.monotonic() < self.suppress_until

    def heard(self, command):
        if self.suspended():
            return
        self.pending = True
        self.heard_at = time.monotonic()
        self.events.put(('wake', command, self.generation))

    def show(self):
        self.desktop.root.deiconify()
        self.desktop.root.lift()

    def ensure_tray(self):
        if self.tray:
            return
        if os.name != 'nt':
            raise RuntimeError('Background tray mode currently supports Windows.')
        import pystray
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (64, 64), '#061725')
        ImageDraw.Draw(image).text((24, 18), 'J', fill='#53e7ff', stroke_width=2)
        self.tray = pystray.Icon('jarvis-omega', image, 'JARVIS / Friday — running', menu=pystray.Menu(
            pystray.MenuItem('Open JARVIS', lambda *_: self.events.put(('show', None, 0)), default=True),
            pystray.MenuItem('Pause background microphone', lambda *_: self.events.put(('pause', None, 0))),
            pystray.MenuItem('Exit JARVIS completely', lambda *_: self.events.put(('exit', None, 0)))))
        try:
            self.tray.run_detached()
        except Exception:
            self.tray = None
            raise

    def hide_to_tray(self):
        try:
            self.ensure_tray()
            self.desktop.root.withdraw()
        except Exception:
            # Keep a taskbar entry if the tray backend is unavailable.
            self.desktop.root.iconify()
            self.desktop._append('SYSTEM', 'Tray unavailable. JARVIS remains running in the taskbar.')

    def enable(self, show_error=True, persist_choice=True):
        if self.enabled and self.listener.ready:
            return True
        d = self.desktop
        try:
            if not settings.enable_mic_input:
                from .settings_ui import update_env_values
                update_env_values({'ENABLE_MIC_INPUT': 'true'})
                object.__setattr__(settings, 'enable_mic_input', True)
            if d.wake_listener.running or getattr(d, '_live_listening', False) or getattr(d, '_live_voice_enabled', False):
                raise RuntimeError('Turn off Wake Word and Live conversation first, then retry.')
            self.ensure_tray()
            self.generation += 1
            self.enabled = True
            self.followup_stop = threading.Event()
            self.listener.start()
            self.retry_failures = 0
            if persist_choice:
                self.preferences['enabled'] = True
                save_preferences(self.preferences)
            d._append('SYSTEM', 'Background microphone READY (local Vosk). Closing the window keeps JARVIS in the tray. Say “Wake up Jarvis”; Friday will answer and listen for your command. Use Exit to stop completely.')
            if '--background' in sys.argv:
                d.root.withdraw()
        except Exception as exc:
            self._stop_listener_only()
            d._append('SYSTEM', 'Background microphone unavailable: ' + str(exc))
            if show_error:
                self.show()
                messagebox.showerror('Background voice', str(exc), parent=d.root)
            return False
        return True

    def _cancel_retry(self):
        retry_id, self.retry_after_id = self.retry_after_id, None
        if retry_id is not None:
            try:
                self.desktop.root.after_cancel(retry_id)
            except Exception:
                pass

    def _stop_listener_only(self):
        self.enabled = False
        self.pending = False
        self.followup_stop.set()
        self.listener.stop()

    def _schedule_retry(self):
        if getattr(self.desktop, '_closing', False) or not self.preferences.get('enabled'):
            return
        self._cancel_retry()
        delays = (3, 10, 30, 60, 120)
        delay = delays[min(self.retry_failures, len(delays) - 1)]
        self.retry_failures += 1
        self.desktop._append('SYSTEM', f'Background microphone recovery will retry in {delay} seconds.')
        self.retry_after_id = self.desktop.root.after(delay * 1000, self.retry_listener)

    def _listener_failed(self, message):
        # A device disconnect must not close the tray or steal focus from the
        # foreground app.  Keep the user's desired setting and recover quietly.
        self.generation += 1
        self._stop_listener_only()
        self.desktop._append('SYSTEM', 'Background listener stopped: ' + message)
        self._schedule_retry()

    def persist(self):
        try:
            save_preferences(self.preferences)
            return True
        except OSError:
            self.desktop._append('SYSTEM', 'Settings could not be saved. Check folder permissions/free disk space. This change may not survive restart.')
            return False

    def disable(self, save=True, show=True):
        self.generation += 1
        self._cancel_retry()
        self._stop_listener_only()
        tray, self.tray = self.tray, None
        try:
            if tray:
                tray.stop()
        except Exception:
            self.desktop._append('SYSTEM', 'Tray cleanup failed; the background microphone is stopped.')
        finally:
            if show:
                self.show()
        if save:
            self.preferences['enabled'] = False
            self.persist()

    def set_startup(self, enabled):
        from .windows_integration import set_startup
        try:
            set_startup(enabled)
            self.desktop._append('SYSTEM', 'Windows sign-in startup ' + ('enabled.' if enabled else 'disabled.'))
            return True
        except Exception as exc:
            messagebox.showerror('Windows startup', str(exc), parent=self.desktop.root)
            return False

    def poll(self):
        try:
            self._poll_events()
        except Exception:
            self.pending = False
            self.desktop._append('SYSTEM', 'Background update failed. Please retry the action.')
        finally:
            if not getattr(self.desktop, '_closing', False):
                self.desktop.root.after(100, self.poll)

    def _poll_events(self):
        d = self.desktop
        if getattr(d, '_closing', False):
            return
        self._refresh_weather()
        if d.voice.state != 'idle':
            self.suppress_until = time.monotonic() + 0.35
        for _ in range(20):
            try:
                kind, value, generation = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'show':
                self.show()
            elif kind == 'pause':
                self.disable()
            elif kind == 'exit':
                d._exit_completely()
                return
            elif generation == self.generation and self.enabled:
                if kind == 'error':
                    self._listener_failed(value)
                elif kind == 'wake':
                    if d.busy:
                        self.pending = False
                        continue
                    if self.preferences.get('show_on_wake'):
                        self.show()
                    if value:
                        self.pending = False
                        self.suppress_until = time.monotonic() + 2
                        d._send_text(value, from_voice=True)
                    else:
                        self._start_followup_capture(generation)
                elif kind == 'followup':
                    self.pending = False
                    payload = value if isinstance(value, dict) else {}
                    listener_error = str(payload.get('listener_error') or '')
                    if listener_error:
                        self._listener_failed(listener_error)
                    command = str(payload.get('text') or '').strip()
                    error = str(payload.get('error') or '').strip()
                    if command:
                        self.suppress_until = time.monotonic() + 2
                        d._send_text(command, from_voice=True)
                    elif error:
                        d._append('SYSTEM', 'Post-wake command capture failed: ' + error)
                        d.voice.speak('Command sun nahi paayi. Please Wake up Jarvis bolkar dobara try kijiye.')
                    else:
                        d._append('SYSTEM', 'Wake acknowledged; no follow-up command was heard.')
                elif kind == 'weather_spoken':
                    d._append('JARVIS', value)
                elif kind == 'brief':
                    self.pending = False
                    if d.busy:
                        continue
                    self.suppress_until = time.monotonic() + 2
                    d._append('JARVIS', value)
                    d.voice.speak(value)

    def _start_followup_capture(self, generation):
        if self.followup_thread and self.followup_thread.is_alive():
            return
        self.followup_stop = threading.Event()
        self._acknowledge()
        self.followup_thread = threading.Thread(
            target=self._followup_worker,
            args=(generation, self.followup_stop),
            daemon=True,
            name='jarvis-background-command',
        )
        self.followup_thread.start()

    def _followup_worker(self, generation, stop_event):
        payload = {'text': '', 'error': '', 'listener_error': ''}
        try:
            if not self.listener.stop(wait=True, timeout=4.0):
                raise RuntimeError('Wake listener did not release the microphone.')
            if not _wait_until_voice_finishes(self.desktop.voice, stop_event):
                if stop_event.is_set():
                    return
                raise RuntimeError('Voice acknowledgement did not finish in time.')
            if stop_event.is_set() or generation != self.generation or not self.enabled:
                return
            # Weather is prefetched while idle; the wake acknowledgement never
            # waits for a weather API. A missing snapshot is stated honestly.
            if self.preferences.get('wake_weather', True):
                snapshot = self.weather_snapshot
                location = self.preferences.get('location')
                if snapshot and snapshot[0] == location and time.monotonic() - snapshot[1] < 300:
                    report = snapshot[2]
                else:
                    report = 'Weather abhi ready nahi hai. Weather now bolkar pooch sakte hain.' if location else 'Mausam ke liye Background Settings mein shehar chuniye.'
                self.events.put(('weather_spoken', report, generation))
                self.desktop.voice.speak(report)
                if not _wait_until_voice_finishes(self.desktop.voice, stop_event, finish_timeout=60.0):
                    raise RuntimeError('Weather speech did not finish; please retry.')
            if stop_event.is_set() or generation != self.generation or not self.enabled:
                return

            if not self.preferences.get('listen_after_wake', True):
                return
            from .microphone import record_until_silence
            from .offline_speech import transcribe_vosk

            def local_transcriber(data, sample_rate, _language):
                return transcribe_vosk(data, sample_rate, self.listener.model_path)

            payload['text'] = record_until_silence(
                language=settings.speech_language,
                max_seconds=float(os.getenv('VOICE_MAX_UTTERANCE_SECONDS', '15')),
                start_timeout=float(os.getenv('VOICE_START_TIMEOUT_SECONDS', '6')),
                silence_seconds=float(os.getenv('VOICE_SILENCE_SECONDS', '0.65')),
                speech_threshold=float(os.getenv('VOICE_VAD_THRESHOLD', '420')),
                stop_event=stop_event,
                transcriber=local_transcriber,
            )
        except Exception as exc:
            payload['error'] = str(exc)
        finally:
            if not stop_event.is_set() and generation == self.generation and self.enabled:
                try:
                    self.listener.start()
                except Exception as exc:
                    payload['listener_error'] = str(exc)
            if not stop_event.is_set():
                self.events.put(('followup', payload, generation))

    def _acknowledge(self):
        from .daily_briefing import wake_greeting
        greeting = wake_greeting(settings.user_name)
        self.desktop._append('JARVIS', greeting)
        if self.preferences.get('fast_ack', True):
            self.desktop.voice.acknowledge(greeting)
        else:
            self.desktop.voice.speak(greeting)
        self.last_wake_latency_ms = round((time.monotonic() - self.heard_at) * 1000) if self.heard_at else None

    def _refresh_weather(self):
        location = self.preferences.get('location')
        if (not self.enabled or not self.preferences.get('wake_weather', True)
                or not valid_location(location) or self.weather_refreshing
                or time.monotonic() < self.weather_next_refresh):
            return
        self.weather_refreshing = True
        self.weather_next_refresh = time.monotonic() + 240
        location = dict(location)
        def worker():
            try:
                from .daily_briefing import rich_weather_report
                self.weather_snapshot = (location, time.monotonic(), rich_weather_report(location))
            finally:
                self.weather_refreshing = False
        threading.Thread(target=worker, daemon=True, name='jarvis-weather-cache').start()

    def health_report(self):
        """Small support snapshot without keys, device names or filesystem paths."""
        from pathlib import Path
        from .wake_model import model_valid
        selected = self.listener.model_path
        model_ready = bool(selected and model_valid(Path(selected).expanduser()))
        startup = Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs/Startup/JARVIS OMEGA Background.lnk'
        sign_in = os.name == 'nt' and bool(os.environ.get('APPDATA')) and startup.is_file()
        return (
            'JARVIS ' + settings.app_version + '\n'
            + 'Wake model: ' + ('ready' if model_ready else 'missing or incomplete') + '\n'
            + 'Microphone listener: ' + ('ready' if self.enabled and self.listener.ready else 'stopped/recovering') + '\n'
            + 'Tray: ' + ('running' if self.tray else 'not active') + '\n'
            + 'Sign-in shortcut: ' + ('present' if sign_in else 'absent') + '\n'
            + 'Listening preference: ' + ('enabled' if self.preferences.get('enabled') else 'disabled') + '\n'
            + 'Wake follow-up: ' + ('listen for command' if self.preferences.get('listen_after_wake', True) else 'acknowledge only') + '\n'
            + 'Wake dispatch latency: ' + (str(self.last_wake_latency_ms) + ' ms (queue only)' if self.last_wake_latency_ms is not None else 'not measured') + '\n'
            + 'Wake focus: ' + ('show window' if self.preferences.get('show_on_wake') else 'stay in background')
        )

    def settings_dialog(self):
        win = tk.Toplevel(self.desktop.root)
        win.title('Background wake and weather')
        win.geometry('640x600')
        win.minsize(480, 350)
        canvas = tk.Canvas(win, highlightthickness=0)
        scroll = ttk.Scrollbar(win, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        frame = ttk.Frame(canvas, padding=18)
        item = canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=e.width))
        ttk.Label(frame, text='Local Vosk listens for Jarvis while the window is closed.\nPC must be awake. Exit stops listening. Select an extracted Vosk model below.').pack(anchor='w')
        status = tk.StringVar(value='ON' if self.enabled else 'OFF')
        ttk.Label(frame, textvariable=status).pack(anchor='w', pady=8)
        def toggle():
            self.disable() if self.enabled else self.enable()
            status.set('ON' if self.enabled else 'OFF')
        ttk.Button(frame, text='Enable / pause background microphone', command=toggle).pack(anchor='w')
        health = tk.StringVar(value='Check background health to see setup status.')
        ttk.Label(frame, textvariable=health, wraplength=520, justify='left').pack(anchor='w', pady=6)
        def check_health():
            health.set(self.health_report())
        ttk.Button(frame, text='Check background health', command=check_health).pack(anchor='w')
        def copy_diagnostics():
            report = self.health_report()
            self.desktop.root.clipboard_clear()
            self.desktop.root.clipboard_append(report)
            health.set('Support diagnostics copied. Paste them when reporting a problem.\n' + report)
        ttk.Button(frame, text='Copy support diagnostics', command=copy_diagnostics).pack(anchor='w', pady=4)
        def retry_now():
            if not self.enabled:
                self.enable()
            status.set('ON' if self.enabled else 'OFF')
            check_health()
        ttk.Button(frame, text='Retry microphone now', command=retry_now).pack(anchor='w', pady=4)
        def enable_always_on():
            if not self.enable():
                status.set('OFF')
                check_health()
                return
            if not self.set_startup(True):
                status.set('ON')
                check_health()
                self.desktop._append('SYSTEM', 'Background wake is ON, but Windows sign-in startup still needs attention.')
                return
            status.set('ON')
            self.hide_to_tray()
        ttk.Button(frame, text='Enable always-on mode (wake + tray + sign-in)', command=enable_always_on).pack(anchor='w', pady=4)
        ttk.Button(frame, text='Start JARVIS when I sign in', command=lambda: self.set_startup(True)).pack(anchor='w', pady=4)
        ttk.Button(frame, text='Disable sign-in startup', command=lambda: self.set_startup(False)).pack(anchor='w')
        for key, label in (
            ('wake_weather', 'Read my city weather and pollution after the name greeting'),
            ('fast_ack', 'Fast wake greeting using the installed offline voice'),
        ):
            variable = tk.BooleanVar(value=self.preferences.get(key, True))
            def save_option(k=key, v=variable):
                self.preferences[k] = v.get()
                self.weather_next_refresh = 0.0
                self.persist()
            ttk.Checkbutton(frame, text=label, variable=variable, command=save_option).pack(anchor='w', pady=3)
        followup = tk.BooleanVar(value=self.preferences.get('listen_after_wake', True))
        def save_followup():
            self.preferences['listen_after_wake'] = followup.get()
            self.persist()
        ttk.Checkbutton(
            frame,
            text='After the wake greeting and optional weather, listen for my command',
            variable=followup,
            command=save_followup,
        ).pack(anchor='w', pady=(10, 2))
        show_on_wake = tk.BooleanVar(value=self.preferences.get('show_on_wake', False))
        def save_show_on_wake():
            self.preferences['show_on_wake'] = show_on_wake.get()
            self.persist()
        ttk.Checkbutton(
            frame,
            text='Bring the JARVIS window forward when the wake phrase is heard',
            variable=show_on_wake,
            command=save_show_on_wake,
        ).pack(anchor='w', pady=2)
        ttk.Label(
            frame,
            text='Keep the second option off for Siri-style background use while Chrome or another app stays in front.',
            wraplength=520,
            justify='left',
        ).pack(anchor='w', pady=(0, 8))
        model_label = tk.StringVar(value='Model: ' + (self.listener.model_path or 'not selected'))
        ttk.Label(frame, textvariable=model_label, wraplength=520).pack(anchor='w', pady=8)
        def select_model():
            folder = filedialog.askdirectory(title='Select extracted Vosk model folder', parent=win)
            if folder:
                if self.enabled:
                    self.disable()
                    status.set('OFF')
                self.listener.model_path = folder
                self.preferences['model_path'] = folder
                self.persist()
                model_label.set('Model: ' + folder)
        ttk.Button(frame, text='Choose Vosk model folder', command=select_model).pack(anchor='w')
        model_events = queue.Queue()
        downloading = [False]
        def download_model():
            if downloading[0]:
                return
            downloading[0] = True
            model_label.set('Preparing official Indian English wake model download (about 36 MB)…')
            def worker():
                try:
                    from .wake_model import install_model
                    path = install_model(settings.db_path.parent / 'models', lambda text: model_events.put(('progress', text)))
                    model_events.put(('done', str(path)))
                except Exception as exc:
                    model_events.put(('error', str(exc)))
            threading.Thread(target=worker, daemon=True).start()
        ttk.Button(frame, text='Download and set up wake model', command=download_model).pack(anchor='w', pady=4)
        automatic = tk.BooleanVar(value=self.preferences.get('auto_updates', False))
        def save_automatic():
            self.preferences['auto_updates'] = automatic.get()
            self.persist()
        ttk.Checkbutton(frame, text='Automatically install verified updates while idle (restarts JARVIS)', variable=automatic, command=save_automatic).pack(anchor='w', pady=8)
        def collect_model():
            if not win.winfo_exists():
                return
            try:
                for _ in range(100):
                    kind, value = model_events.get_nowait()
                    if kind == 'done':
                        downloading[0] = False
                        self.listener.model_path = value
                        self.preferences['model_path'] = value
                        self.persist()
                        model_label.set('Model ready. Enable background microphone above.')
                    elif kind == 'error':
                        downloading[0] = False
                        model_label.set('Model setup failed: ' + value)
                    else:
                        model_label.set(value)
            except queue.Empty:
                pass
            win.after(100, collect_model)
        collect_model()
        current = self.preferences.get('location') or {}
        location_label = tk.StringVar(value='Weather location: ' + current.get('name', 'not selected'))
        ttk.Label(frame, textvariable=location_label).pack(anchor='w', pady=(16, 4))
        entry = ttk.Entry(frame, width=42)
        entry.pack(fill='x')
        results = tk.Listbox(frame, width=64, height=5)
        results.pack(fill='x', pady=5)
        locations = []
        replies = queue.Queue()
        searching = [False]
        def search():
            if searching[0]:
                return
            searching[0] = True
            city = entry.get()
            location_label.set('Searching Open-Meteo…')
            def worker():
                try:
                    replies.put((find_locations(city), None))
                except Exception:
                    replies.put(([], 'City search unavailable. Check spelling and internet.'))
            threading.Thread(target=worker, daemon=True).start()
        def collect():
            if not win.winfo_exists():
                return
            try:
                rows, error = replies.get_nowait()
                locations[:] = rows
                results.delete(0, 'end')
                for row in rows:
                    results.insert('end', ', '.join(str(row.get(k, '')) for k in ('name', 'admin1', 'country')))
                location_label.set(error or 'Select your city from the results.' if rows or error else 'No matching city found.')
                searching[0] = False
            except queue.Empty:
                pass
            win.after(100, collect)
        def select():
            if not results.curselection():
                return
            row = locations[results.curselection()[0]]
            self.preferences['location'] = {k: row[k] for k in ('name', 'latitude', 'longitude')}
            self.weather_snapshot = None
            self.weather_next_refresh = 0.0
            if not self.persist():
                return
            location_label.set('Weather location: ' + row['name'])
        ttk.Button(frame, text='Search city', command=search).pack(side='left')
        ttk.Button(frame, text='Save selected city', command=select).pack(side='left', padx=8)
        collect()

    def retry_listener(self):
        self.retry_after_id = None
        if getattr(self.desktop, '_closing', False) or not self.preferences.get('enabled') or self.enabled:
            return
        # Device recovery and listener shutdown can take longer than one timer.
        # Keep retrying without opening a modal dialog over a hidden desktop.
        if not self.enable(show_error=False, persist_choice=False):
            self._schedule_retry()


def install_background_ui():
    from .gui import JarvisDesktop
    if getattr(JarvisDesktop, '_background_installed', False):
        return
    original_init, original_close = JarvisDesktop.__init__, JarvisDesktop._close
    def init(self, root):
        original_init(self, root)
        self.background = BackgroundController(self)
        from .update_ui import schedule_update_checks
        schedule_update_checks(self)
        bar = ttk.Frame(root)
        bar.pack(side='bottom', fill='x')
        ttk.Button(bar, text='BACKGROUND / WEATHER', command=self.background.settings_dialog).pack(side='left', padx=8)
        from .account_ui import show_account_dialog
        ttk.Button(bar, text='ACCOUNT / SUBSCRIPTION', command=lambda: show_account_dialog(self)).pack(side='left', padx=8)
        ttk.Button(bar, text='AQI', command=lambda: self._send_text('air quality')).pack(side='left', padx=4)
        ttk.Button(bar, text='TOMORROW', command=lambda: self._send_text('tomorrow weather')).pack(side='left', padx=4)
        ttk.Button(bar, text='WEATHER NOW', command=lambda: self._send_text('weather report')).pack(side='left', padx=8)
        ttk.Button(bar, text='EXIT COMPLETELY', command=self._exit_completely).pack(side='right', padx=8)
        root.protocol('WM_DELETE_WINDOW', self._close)
        if '--background' in sys.argv:
            # A sign-in shortcut is not proof that the microphone is listening.
            # Keep setup visible if the saved listener could not start.
            root.after(1200, lambda: self.background.hide_to_tray() if self.background.enabled else None)
    def close(self):
        self.background.hide_to_tray()
    def exit_completely(self):
        from .youtube_player import shutdown
        try:
            self.background.disable(save=False)
        finally:
            try:
                shutdown()
            finally:
                original_close(self)
    JarvisDesktop.__init__ = init
    JarvisDesktop._close = close
    JarvisDesktop._exit_completely = exit_completely
    JarvisDesktop._background_installed = True
