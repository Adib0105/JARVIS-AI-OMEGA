"""Exercise the real desktop lifecycle in a fresh packaged CI installation."""
import json
import sys
from pathlib import Path


def report_path():
    if '--jarvis-desktop-smoke' not in sys.argv:
        return None
    index = sys.argv.index('--jarvis-desktop-smoke')
    return Path(sys.argv[index + 1])


def schedule_smoke_check(root, app):
    path = report_path()
    if path is None:
        return
    errors = []
    root.report_callback_exception = lambda kind, exc, tb: errors.append(kind.__name__)
    def finish():
        try:
            assert root.winfo_exists() and root.winfo_viewable(), 'Desktop not visible'
            assert app.jarvis.memory.get_session(app.jarvis.session_id), 'Core did not initialize'
            assert app.hud and app.hud.find_all(), 'Avatar did not render'
            for canvas in app.sidebar_canvases:
                assert canvas.bbox('all'), 'Sidebar content missing'
                canvas.yview_moveto(1)
                root.update_idletasks()
                assert canvas.yview()[1] > 0.99, 'Sidebar bottom inaccessible'
                canvas.yview_moveto(0)
            for state in ('listening', 'thinking', 'speaking', 'idle'):
                app.hud.set_state(state)
                app.hud._portrait()
            assert 'Friday' in app.jarvis.chat('what is your name'), 'Identity route failed'
            from .connection_setup import open_connection_setup
            import tkinter as tk
            connection = open_connection_setup(app)
            from .config import settings
            session = app.jarvis.session_id
            connection.connection_key_entry.insert(0, 'ci-synthetic-key-not-a-credential')
            connection.connection_save_button.invoke()
            assert settings.api_key == 'ci-synthetic-key-not-a-credential', 'Saved key not applied live'
            assert app.jarvis.provider.client is not None, 'Provider not rebuilt after saving'
            assert app.jarvis.session_id == session, 'Saving key reset the conversation'
            assert not connection.connection_key_entry.get(), 'Key entry not cleared after save'
            root.update_idletasks()
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()
            from .account_ui import show_account_dialog
            account = show_account_dialog(app)
            account.account_tabs.select(1)
            root.update_idletasks()
            account.account_canvas.yview_moveto(1)
            root.update_idletasks()
            assert account.account_canvas.yview()[1] > 0.99, 'Subscription controls inaccessible'
            account.destroy()
            # Change focus to another real window, then minimize and close-to-tray.
            other = tk.Toplevel(root)
            other.title('Another application focus check')
            other.focus_force()
            root.update()
            assert root.winfo_exists() and not getattr(app, '_closing', False)
            other.destroy()
            root.iconify()
            root.update()
            assert root.winfo_exists() and not getattr(app, '_closing', False)
            app.background.show()
            app._close()
            root.update()
            assert root.winfo_exists() and not getattr(app, '_closing', False), 'Close stopped the app'
            assert 'Friday' in app.jarvis.chat('hello'), 'Hidden desktop stopped handling commands'
            app.background.show()
            root.update()
            try:
                from PIL import ImageGrab
                ImageGrab.grab().save(path.with_suffix('.png'))
            except Exception:
                pass
            assert not errors, 'Tk callback failures: ' + ', '.join(errors)
            app._exit_completely()
            path.write_text(json.dumps({'ok': True, 'desktop_rendered': True, 'closed': True}), encoding='utf-8')
        except Exception as exc:
            from .logging_utils import redact_text
            path.write_text(json.dumps({'ok': False, 'error': redact_text(str(exc)), 'type': type(exc).__name__}), encoding='utf-8')
            try:
                app._exit_completely()
            except Exception:
                root.destroy()
    root.after(1800, finish)
