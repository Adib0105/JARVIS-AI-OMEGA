import json
import os
import sys
from pathlib import Path

from jarvis.logging_utils import configure_logging, install_exception_hook
from jarvis.product_paths import PATHS
from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
from jarvis.skill_runtime_extension import install_skill_runtime
from jarvis.ui_release_extension import install_release_ui
from jarvis.ui_skill_extension import install_skill_ui
from jarvis.voice_ui import install_voice_ui


def packaged_healthcheck() -> int:
    """Non-interactive packaged-app validation used by installer CI and support diagnostics."""
    try:
        configure_logging()
        probe = PATHS.data_dir / 'package-healthcheck.tmp'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        payload = {
            'status': 'PASS',
            'frozen': bool(getattr(sys, 'frozen', False)),
            'executable': str(Path(sys.executable).resolve()),
            'install_dir': str(PATHS.install_dir),
            'data_dir': str(PATHS.data_dir),
            'config_dir': str(PATHS.config_dir),
            'log_dir': str(PATHS.log_dir),
            'database': str(PATHS.data_dir / 'jarvis.db'),
            'exports': str(PATHS.export_dir),
            'cwd': os.getcwd(),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload['frozen'] else 2
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if '--package-healthcheck' in sys.argv:
        raise SystemExit(packaged_healthcheck())
    install_exception_hook()
    install_runtime_guards()
    install_voice_ui()
    install_release_ui()
    install_skill_runtime()
    install_skill_ui()
    run_adaptive_gui()
