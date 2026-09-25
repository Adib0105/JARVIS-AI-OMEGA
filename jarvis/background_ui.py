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
from .daily_briefing import build_briefing, find_locations, valid_location
from .wake_service import BackgroundWakeListener


def preference_path():
    return settings.db_path.parent / 'background-settings.json'


def load_preferences():
    try:
        data = json.loads(preference_path().read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        clean = {'enabled': data.get('enabled') is True}
        if 'auto_updates' in data:
            clean['auto_updates'] = data.get('auto_updates') is True
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


class BackgroundController:
    def __init__(self, desktop):
        self.desktop = desktop
        self.events = queue.Queue()
        self.preferences = load_preferences()
        self.enabled = False
        self.pending = False
        self.suppress_until = 0.0
        self.generation = 0
        self.tray = None
        from .wake_model import MODEL_NAME, model_valid
        installed_model = settings.db_path.parent / 'models' / MODEL_NAME
        selected_model = self.preferences.get('model_path') or settings.vosk_model_path
        if not selected_model and model_valid(installed_model):
            selected_model = str(installed_model)
        self.listener = BackgroundWakeListener(selected_model, self.heard,
            lambda error: self.events.put(('error', error, self.generation)), self.suspended, settings.wake_word)
        desktop.root.after(100, self.poll)
        if self.preferences.get('enabled'):
            desktop.root.after(1000, self.enable)

    def suspended(self):
        d = self.desktop
        return not self.enabled or self.pending or d.busy or d.voice.state != 'idle' or time.monotonic() < self.suppress_until

    def heard(self, command):
        if self.suspended():
            return
        self.pending = True
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

    def enable(self, show_error=True):
        if self.enabled:
            return
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
            self.listener.start()
            self.preferences['enabled'] = True
            save_preferences(self.preferences)
            d._append('SYSTEM', 'Background microphone ON (local Vosk). Closing the window keeps JARVIS in the tray. Say Jarvis to wake it. Use Exit to stop completely.')
            if '--background' in sys.argv:
                d.root.withdraw()
        except Exception as exc:
            self.disable(save=False)
            d._append('SYSTEM', 'Background microphone unavailable: ' + str(exc))
            if show_error:
                self.show()
                messagebox.showerror('Background voice', str(exc), parent=d.root)
            return False
        return True

    def persist(self):
        try:
            save_preferences(self.preferences)
            return True
        except OSError:
            self.desktop._append('SYSTEM', 'Settings could not be saved. Check folder permissions/free disk space. This change may not survive restart.')
            return False

    def disable(self, save=True):
        self.generation += 1
        self.enabled = False
        self.pending = False
        self.listener.stop()
        tray, self.tray = self.tray, None
        try:
            if tray:
                tray.stop()
        except Exception:
            self.desktop._append('SYSTEM', 'Tray cleanup failed; the background microphone is stopped.')
        finally:
            self.show()
        if save:
            self.preferences['enabled'] = False
            self.persist()

    def set_startup(self, enabled):
        from .windows_integration import set_startup
        try:
            set_startup(enabled)
            self.desktop._append('SYSTEM', 'Windows sign-in startup ' + ('enabled.' if enabled else 'disabled.'))
        except Exception as exc:
            messagebox.showerror('Windows startup', str(exc), parent=self.desktop.root)

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
        if d.voice.state != 'idle':
            self.suppress_until = time.monotonic() + 1.2
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
                    # A transient device failure must not erase sign-in preference.
                    self.disable(save=False)
                    d._append('SYSTEM', 'Background listener stopped: ' + value)
                    if self.preferences.get('enabled'):
                        d.root.after(30000, self.retry_listener)
                elif kind == 'wake':
                    if d.busy:
                        self.pending = False
                        continue
                    self.show()
                    if value:
                        self.pending = False
                        self.suppress_until = time.monotonic() + 2
                        d._send_text(value, from_voice=True)
                    else:
                        location = self.preferences.get('location')
                        def briefing_worker(loc=location, gen=generation):
                            try:
                                text = build_briefing(loc)
                            except Exception:
                                text = 'Briefing abhi available nahi hai. Dobara try kijiye.'
                            self.events.put(('brief', text, gen))
                        threading.Thread(target=briefing_worker, daemon=True).start()
                elif kind == 'brief':
                    self.pending = False
                    if d.busy:
                        continue
                    self.suppress_until = time.monotonic() + 2
                    d._append('JARVIS', value)
                    d.voice.speak(value)

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
        ttk.Button(frame, text='Start JARVIS when I sign in', command=lambda: self.set_startup(True)).pack(anchor='w', pady=4)
        ttk.Button(frame, text='Disable sign-in startup', command=lambda: self.set_startup(False)).pack(anchor='w')
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
            if not self.persist():
                return
            location_label.set('Weather location: ' + row['name'])
        ttk.Button(frame, text='Search city', command=search).pack(side='left')
        ttk.Button(frame, text='Save selected city', command=select).pack(side='left', padx=8)
        collect()

    def retry_listener(self):
        if getattr(self.desktop, '_closing', False) or not self.preferences.get('enabled') or self.enabled:
            return
        # Device recovery and listener shutdown can take longer than one timer.
        # Keep retrying without opening a modal dialog over a hidden desktop.
        if not self.enable(show_error=False):
            self.desktop.root.after(30000, self.retry_listener)


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
