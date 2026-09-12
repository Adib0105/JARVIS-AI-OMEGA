import sys

# Dispatch before importing any GUI/runtime extension in a frozen speech child.
if __name__ == '__main__' and sys.argv[1:2] == ['--jarvis-speech-worker']:
    from jarvis.speech_worker import main as speech_main
    raise SystemExit(speech_main(sys.argv[2:]))

if __name__ == '__main__' and sys.argv[1:2] == ['--jarvis-background-check']:
    from jarvis.background_check import main as background_check
    raise SystemExit(background_check())

from jarvis.background_ui import install_background_ui
from jarvis.chat_workspace_ui import install_chat_workspace
from jarvis.fast_runtime import install_fast_command_runtime
from jarvis.logging_utils import install_exception_hook
from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
from jarvis.skill_runtime_extension import install_skill_runtime
from jarvis.ui_release_extension import install_release_ui
from jarvis.ui_skill_extension import install_skill_ui
from jarvis.voice_ui import install_voice_ui


if __name__ == '__main__':
    from jarvis.desktop_instance import acquire_desktop_instance
    if not acquire_desktop_instance():
        from tkinter import messagebox
        messagebox.showinfo('JARVIS is running', 'Open JARVIS from its taskbar or system tray icon. Exit that instance before starting another.')
        raise SystemExit(0)
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
