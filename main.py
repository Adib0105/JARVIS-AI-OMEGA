from jarvis.logging_utils import install_exception_hook
from jarvis.ui import run_cli


if __name__ == '__main__':
    install_exception_hook()
    run_cli()
