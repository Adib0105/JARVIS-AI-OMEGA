import json
import os
import subprocess
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
        import importlib.util

        dependency_status = {
            name: importlib.util.find_spec(name) is not None
            for name in ('edge_tts', 'pyttsx3', 'pyautogui', 'sounddevice', 'speech_recognition')
        }
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
            'runtime_dependencies': dependency_status,
        }
        if os.name == 'nt' and not all(dependency_status.values()):
            payload['status'] = 'FAIL'
            payload['error'] = 'One or more packaged Windows runtime dependencies are missing.'
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload['status'] == 'PASS' and payload['frozen'] else 2
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


def tts_worker_healthcheck() -> int:
    try:
        from jarvis.tts_worker import runtime_healthcheck

        payload = runtime_healthcheck()
        payload['frozen'] = bool(getattr(sys, 'frozen', False))
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload.get('status') == 'PASS' and payload['frozen'] else 1
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 1


def packaged_tts_healthcheck() -> int:
    """Verify the frozen EXE can enter its TTS worker path without launching the GUI."""
    if not bool(getattr(sys, 'frozen', False)):
        print(json.dumps({'status': 'FAIL', 'frozen': False, 'error': 'Packaged TTS check requires frozen EXE.'}))
        return 2
    try:
        completed = subprocess.run(
            [sys.executable, '--tts-worker-healthcheck'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        payload = {
            'status': 'PASS' if completed.returncode == 0 else 'FAIL',
            'frozen': True,
            'worker_exit_code': completed.returncode,
            'worker_started_without_gui': completed.returncode == 0,
        }
        if completed.stdout.strip():
            try:
                payload['worker'] = json.loads(completed.stdout.strip().splitlines()[-1])
            except Exception:
                payload['worker_output_present'] = True
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload['status'] == 'PASS' else 1
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'frozen': True, 'error': str(exc)}, ensure_ascii=False))
        return 1


def _is_edge_playback_worker_invocation() -> bool:
    return len(sys.argv) >= 3 and sys.argv[1] == '-m' and sys.argv[2] == 'edge_playback'


def _is_offline_playback_worker_invocation() -> bool:
    return len(sys.argv) >= 2 and sys.argv[1] == '--offline-tts-playback'


def main() -> int:
    if '--tts-worker-healthcheck' in sys.argv:
        return tts_worker_healthcheck()

    if _is_edge_playback_worker_invocation():
        from jarvis.tts_worker import run_edge_playback_worker

        return run_edge_playback_worker(sys.argv[3:])

    if _is_offline_playback_worker_invocation():
        from jarvis.offline_tts_worker import run_offline_playback_worker

        return run_offline_playback_worker(sys.argv[2:])

    if '--package-healthcheck' in sys.argv:
        return packaged_healthcheck()
    if '--first-run-healthcheck' in sys.argv:
        return first_run_healthcheck()
    if '--tts-runtime-healthcheck' in sys.argv:
        return packaged_tts_healthcheck()

    background = '--background' in sys.argv

    # Resolve the active local account BEFORE Settings/JarvisOmega are imported so
    # USER_NAME and per-profile memory/audit paths are isolated correctly.
    from jarvis.accounts import run_account_gate

    profile = run_account_gate(background=background)
    if profile is None:
        return 0

    # Provider bootstrap remains device-level configuration, while memory/export
    # state is profile-specific through environment values selected above.
    from jarvis.first_run import run_first_run_setup

    if not run_first_run_setup():
        return 0

    from jarvis.logging_utils import install_exception_hook
    from jarvis.runtime_guard import run_adaptive_gui

    install_exception_hook()
    run_adaptive_gui(background=background)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
