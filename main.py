from jarvis.logging_utils import install_exception_hook
from jarvis.runtime_guard import install_runtime_guards
from jarvis.skill_runtime_extension import install_skill_runtime
from jarvis.ui import run_cli


if __name__ == '__main__':
    install_exception_hook()
    install_runtime_guards()
    install_skill_runtime()
    run_cli()
