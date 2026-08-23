from jarvis.fast_runtime import install_fast_command_runtime
from jarvis.logging_utils import install_exception_hook
from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
from jarvis.skill_runtime_extension import install_skill_runtime
from jarvis.ui_release_extension import install_release_ui
from jarvis.ui_skill_extension import install_skill_ui
from jarvis.voice_ui import install_voice_ui


if __name__ == '__main__':
    install_exception_hook()
    install_runtime_guards()
    install_fast_command_runtime()
    install_voice_ui()
    install_release_ui()
    install_skill_runtime()
    install_skill_ui()
    run_adaptive_gui()
