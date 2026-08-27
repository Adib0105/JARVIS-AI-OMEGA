from __future__ import annotations

import importlib
import platform
import sys

from jarvis.diagnostics import DiagnosticResult, DiagnosticState


RESULTS: list[DiagnosticResult] = []
MINIMUM_PYTHON = (3, 11)


def report(name: str, state: DiagnosticState, detail: str = '', *, required: bool = False) -> None:
    result = DiagnosticResult(name, state, detail, required)
    RESULTS.append(result)
    print(result.line())


def module_state(label: str, module_name: str, *, required: bool = False) -> bool:
    try:
        module = importlib.import_module(module_name)
        report(label, DiagnosticState.INSTALLED, getattr(module, '__version__', 'installed'), required=required)
        return True
    except Exception as exc:
        report(
            label,
            DiagnosticState.FAILED if required else DiagnosticState.DEGRADED,
            f'{type(exc).__name__}: {exc}',
            required=required,
        )
        return False


def main() -> int:
    RESULTS.clear()
    python_ok = sys.version_info >= MINIMUM_PYTHON
    report(
        'Python runtime',
        DiagnosticState.LOCAL_FUNCTIONAL if python_ok else DiagnosticState.FAILED,
        f'{platform.python_version()} (minimum {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]})',
        required=True,
    )

    for label, module_name in (
        ('OpenAI-compatible SDK', 'openai'),
        ('Rich terminal UI', 'rich'),
        ('Public web search package', 'ddgs'),
        ('System telemetry package', 'psutil'),
        ('PDF package', 'pypdf'),
        ('DOCX package', 'docx'),
        ('Excel package', 'openpyxl'),
    ):
        module_state(label, module_name, required=True)

    pillow = module_state('Image processing package', 'PIL', required=True)
    edge = module_state('Edge TTS package', 'edge_tts')
    offline_tts = module_state('Offline TTS package', 'pyttsx3')
    desktop = module_state('Desktop input package', 'pyautogui')
    sound = module_state('Audio capture package', 'sounddevice')
    speech = module_state('Speech recognition package', 'speech_recognition')

    report(
        'Image/screen feature device verification',
        DiagnosticState.NOT_TESTED,
        'Pillow is installed.' if pillow else 'Image package missing; device path not exercised.',
    )
    report(
        'TTS audible speaker output',
        DiagnosticState.NOT_TESTED,
        'Backend package present; this diagnostic does not claim audible output.' if (edge or offline_tts)
        else 'No TTS backend package is currently available.',
    )
    report(
        'Microphone capture / speech recognition',
        DiagnosticState.NOT_TESTED,
        'Packages present; no physical microphone was exercised.' if (sound and speech)
        else 'One or more microphone packages are unavailable; no device test was performed.',
    )
    report(
        'Computer-use keyboard/mouse device verification',
        DiagnosticState.NOT_TESTED,
        'Automation package present; no real desktop action was verified.' if desktop
        else 'Desktop automation package unavailable; no device test was performed.',
    )

    try:
        from jarvis import __version__
        from jarvis.capability_registry import CapabilityRegistry
        from jarvis.config import settings
        from jarvis.config_validation import ValidationLevel, validate_settings
        from jarvis.memory_v7 import V7MemoryStore
        from jarvis.observability import ObservabilityManager
        from jarvis.storage import BackupManager, TARGET_SCHEMA_VERSION
        from jarvis.version import APP_VERSION

        consistent = __version__ == settings.app_version == APP_VERSION
        report(
            'Application version consistency',
            DiagnosticState.LOCAL_FUNCTIONAL if consistent else DiagnosticState.FAILED,
            f'package={__version__}; config={settings.app_version}; canonical={APP_VERSION}',
            required=True,
        )

        findings = validate_settings(settings)
        failures = [item for item in findings if item.level == ValidationLevel.FAIL]
        warnings = [item for item in findings if item.level == ValidationLevel.WARNING]
        if failures:
            report(
                'Runtime configuration validation',
                DiagnosticState.FAILED,
                '; '.join(f'{item.key}: {item.message}' for item in failures)[:1500],
                required=True,
            )
        elif warnings:
            report(
                'Runtime configuration validation',
                DiagnosticState.DEGRADED,
                '; '.join(f'{item.key}: {item.message}' for item in warnings)[:1500],
            )
        else:
            report('Runtime configuration validation', DiagnosticState.CONFIGURED, 'no validation findings')

        key_name = 'OPENROUTER_API_KEY' if settings.provider == 'openrouter' else 'OPENAI_API_KEY'
        placeholders = {'put_your_openrouter_key_here', 'put_your_api_key_here', 'YAHAN_APNI_OPENROUTER_KEY'}
        key_configured = bool(settings.api_key and settings.api_key not in placeholders)
        report(
            'AI provider configuration',
            DiagnosticState.CONFIGURED if key_configured else DiagnosticState.DEGRADED,
            f'provider={settings.provider}; model={settings.model}; {key_name}=' + ('configured' if key_configured else 'missing/placeholder'),
        )
        report(
            'Live AI provider inference',
            DiagnosticState.NOT_TESTED,
            'No live provider request is made by self_check.py; successful inference requires separate evidence.',
        )

        memory = V7MemoryStore(settings.db_path)
        memory_stats = memory.v7_stats()
        schema_ok = memory_stats.get('schema_version') == TARGET_SCHEMA_VERSION
        report(
            'SQLite schema migration',
            DiagnosticState.LOCAL_FUNCTIONAL if schema_ok else DiagnosticState.FAILED,
            f"schema={memory_stats.get('schema_version')} target={TARGET_SCHEMA_VERSION}",
            required=True,
        )

        capabilities = CapabilityRegistry().snapshot(refresh=True)
        broken = [item['name'] for item in capabilities if item['status'] == 'BROKEN']
        report(
            'Capability Registry local check',
            DiagnosticState.LOCAL_FUNCTIONAL if not broken else DiagnosticState.DEGRADED,
            f'capabilities={len(capabilities)}; broken={broken}',
        )

        usage = ObservabilityManager(settings.db_path).usage_summary('today')
        report(
            'Observability database',
            DiagnosticState.LOCAL_FUNCTIONAL if isinstance(usage, dict) else DiagnosticState.FAILED,
            'local event store query completed',
            required=True,
        )

        integrity = BackupManager(settings.db_path).integrity_check()
        report(
            'Database integrity',
            DiagnosticState.LOCAL_FUNCTIONAL if integrity.get('ok') is True else DiagnosticState.FAILED,
            str(integrity.get('result') or integrity),
            required=True,
        )

        report(
            'Production self-modification policy',
            DiagnosticState.CONFIGURED if not settings.production_self_modification else DiagnosticState.DEGRADED,
            'disabled by default' if not settings.production_self_modification else 'enabled deliberately; human approval/release gates still required',
        )
    except Exception as exc:
        report(
            'JARVIS core diagnostics',
            DiagnosticState.FAILED,
            f'{type(exc).__name__}: {exc}',
            required=True,
        )

    report(
        'Real Windows device E2E',
        DiagnosticState.NOT_TESTED,
        'GUI focus, DPI/resolution, microphone, audible TTS, real browser/UIA and live-provider behavior require separate real-machine evidence.',
    )

    required_failures = [item for item in RESULTS if item.required and item.failed]
    print('\nAUTOMATED DIAGNOSTIC RESULT:', 'FAILED' if required_failures else 'COMPLETE')
    print('Device/live/E2E states above remain NOT_TESTED unless separately verified with evidence.')
    return 1 if required_failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
