from __future__ import annotations

import os
import platform
import sys


def check(label: str, ok: bool, detail: str = '') -> bool:
    tag = 'PASS' if ok else 'FAIL'
    print(f'[{tag}] {label}' + (f' - {detail}' if detail else ''))
    return ok


def main() -> None:
    results = []
    results.append(check('Python >= 3.10', sys.version_info >= (3, 10), platform.python_version()))
    try:
        import openai
        results.append(check('OpenAI SDK', True, getattr(openai, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('OpenAI SDK', False, str(exc)))
    try:
        import rich
        results.append(check('Rich terminal UI', True, 'installed'))
    except Exception as exc:
        results.append(check('Rich terminal UI', False, str(exc)))
    try:
        import pyttsx3
        results.append(check('Spoken reply engine', True, getattr(pyttsx3, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('Spoken reply engine', False, str(exc)))
    try:
        from jarvis.config import settings
        results.append(check('API key configured', bool(settings.api_key and settings.api_key != 'put_your_api_key_here'), settings.model))
        results.append(check('Voice output enabled', settings.enable_voice_output, f'rate={settings.voice_rate}, volume={settings.voice_volume}'))
        results.append(check('Microphone input', True, 'not installed by design'))
        results.append(check('Database folder writable', os.access(settings.db_path.parent, os.W_OK) if settings.db_path.parent.exists() else True, str(settings.db_path)))
        roots = [str(p) for p in settings.allowed_file_roots if p.exists()]
        results.append(check('Local roots', bool(roots), '; '.join(roots) or 'none'))
    except Exception as exc:
        results.append(check('JARVIS config', False, str(exc)))
    print('\nJARVIS OMEGA:', 'READY' if all(results) else 'NEEDS ATTENTION')


if __name__ == '__main__':
    main()
