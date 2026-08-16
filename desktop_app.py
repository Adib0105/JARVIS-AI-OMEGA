from jarvis.logging_utils import install_exception_hook
from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
from jarvis.voice_ui import install_voice_ui


if __name__ == '__main__':
    install_exception_hook()
    install_runtime_guards()
    install_voice_ui()
    run_adaptive_gui()
