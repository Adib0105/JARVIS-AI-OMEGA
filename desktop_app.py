import json
import os
import sys
from pathlib import Path

from jarvis.product_paths import PATHS


def packaged_healthcheck() -> int:
    """Non-interactive packaged-app validation used by installer CI and support diagnostics."""
    try:
        from jarvis.logging_utils import configure_logging

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


def first_run_healthcheck() -> int:
    """Verify a fresh packaged install reaches bootstrap state without importing the AI core."""
    try:
        from jarvis.first_run import inspect_bootstrap_state
        from jarvis.product_paths import config_env_path

        state = inspect_bootstrap_state()
        config_path = config_env_path().resolve()
        install_dir = PATHS.install_dir.resolve()
        payload = {
            'status': 'PASS',
            'frozen': bool(getattr(sys, 'frozen', False)),
            'bootstrap_ready': state.ready,
            'provider': state.provider,
            'key_present': state.key_present,
            'local_fallback_configured': state.local_fallback_configured,
            'config_path': str(config_path),
            'config_under_user_data': PATHS.config_dir.resolve() in config_path.parents,
            'config_outside_install_dir': install_dir not in config_path.parents,
        }
        if payload['bootstrap_ready']:
            payload['status'] = 'FAIL'
            payload['error'] = 'Fresh-install bootstrap unexpectedly found a configured online credential.'
        if not payload['config_under_user_data'] or not payload['config_outside_install_dir']:
            payload['status'] = 'FAIL'
            payload['error'] = 'Packaged configuration path is not isolated to writable per-user data.'
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload['status'] == 'PASS' and payload['frozen'] else 1
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 1


def main() -> int:
    if '--package-healthcheck' in sys.argv:
        return packaged_healthcheck()
    if '--first-run-healthcheck' in sys.argv:
        return first_run_healthcheck()

    # Bootstrap must happen before importing modules that materialize global
    # Settings/JarvisOmega. A fresh packaged install therefore reaches a proper
    # setup UI instead of failing strict AI configuration validation at import/startup.
    from jarvis.first_run import run_first_run_setup

    if not run_first_run_setup():
        return 0

    from jarvis.logging_utils import install_exception_hook
    from jarvis.runtime_guard import install_runtime_guards, run_adaptive_gui
    from jarvis.skill_runtime_extension import install_skill_runtime
    from jarvis.ui_release_extension import install_release_ui
    from jarvis.ui_skill_extension import install_skill_ui
    from jarvis.voice_ui import install_voice_ui

    install_exception_hook()
    install_runtime_guards()
    install_voice_ui()
    install_release_ui()
    install_skill_runtime()
    install_skill_ui()
    run_adaptive_gui()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
