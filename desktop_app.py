from jarvis.gui import run_gui
from jarvis.logging_utils import install_exception_hook


if __name__ == '__main__':
    install_exception_hook()
    run_gui()
