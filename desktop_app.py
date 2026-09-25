import sys
from pathlib import Path

if __name__ == '__main__' and sys.argv[1:2] == ['--jarvis-speech-check']:
    from jarvis.speech_check import main as speech_check
    raise SystemExit(speech_check())

# Dispatch before importing any GUI/runtime extension in a frozen speech child.
if __name__ == '__main__' and sys.argv[1:2] == ['--jarvis-speech-worker']:
    from jarvis.speech_worker import main as speech_main
    raise SystemExit(speech_main(sys.argv[2:]))

if __name__ == '__main__' and sys.argv[1:2] == ['--jarvis-background-check']:
    from jarvis.background_check import main as background_check
    raise SystemExit(background_check())

def main():
    from jarvis.desktop_instance import acquire_desktop_instance, show_existing_desktop
    if not acquire_desktop_instance():
        if show_existing_desktop():
            raise SystemExit(0)
        from tkinter import messagebox
        messagebox.showinfo('JARVIS is running', 'Open JARVIS from its taskbar or system tray icon. Exit that instance before starting another.')
        raise SystemExit(0)

    # Packaged smoke tests must remain unattended.  Every ordinary desktop run
    # uses the local account/session flow before config/database modules import,
    # which is what makes per-profile storage isolation deterministic.
    if '--jarvis-desktop-smoke' not in sys.argv:
        from jarvis.user_profiles import authenticate_desktop
        app_root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        profile = authenticate_desktop(
            legacy_data_dir=app_root / 'data',
            background='--background' in sys.argv,
        )
        if profile is None:
            raise SystemExit(0)

    from jarvis.background_ui import install_background_ui
    from jarvis.chat_workspace_ui import install_chat_workspace
    from jarvis.fast_runtime import install_fast_command_runtime
    from jarvis.logging_utils import install_exception_hook
    from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
    from jarvis.skill_runtime_extension import install_skill_runtime
    from jarvis.ui_release_extension import install_release_ui
    from jarvis.ui_skill_extension import install_skill_ui
    from jarvis.voice_ui import install_voice_ui
    install_exception_hook()
    install_runtime_guards()
    install_fast_command_runtime()
    install_voice_ui()
    install_release_ui()
    install_skill_runtime()
    install_skill_ui()
    install_chat_workspace()
    install_background_ui()
    run_adaptive_gui()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import json
        import tempfile
        from pathlib import Path
        try:
            from jarvis.logging_utils import redact_text
        except Exception:
            import re
            def redact_text(value):
                return re.sub(r'sk-[A-Za-z0-9_-]+', '[REDACTED]', str(value))
        # Do not show a blocking error dialog in unattended package verification.
        if '--jarvis-desktop-smoke' in sys.argv:
            report = Path(sys.argv[sys.argv.index('--jarvis-desktop-smoke') + 1])
            report.write_text(json.dumps({'ok': False, 'error': redact_text(str(exc))}), encoding='utf-8')
        else:
            import traceback
            report = Path(tempfile.gettempdir()) / 'jarvis-startup-error.txt'
            report.write_text(redact_text(traceback.format_exc()), encoding='utf-8')
            from tkinter import messagebox
            messagebox.showerror('JARVIS could not start',
                'Please extract the entire ZIP before opening JARVIS. Keep the _internal folder beside the EXE.\n\n'
                + redact_text(str(exc))[:400] + '\n\nStartup report: ' + str(report))
        raise SystemExit(1)
