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
        results.append(check('OpenAI-compatible SDK', True, getattr(openai, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('OpenAI-compatible SDK', False, str(exc)))
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

        provider_ok = settings.provider in {'openrouter', 'openai'}
        results.append(check('AI provider', provider_ok, settings.provider))

        placeholder = 'put_your_openrouter_key_here' if settings.provider == 'openrouter' else 'put_your_api_key_here'
        key_ok = bool(settings.api_key and settings.api_key != placeholder)
        key_name = 'OPENROUTER_API_KEY' if settings.provider == 'openrouter' else 'OPENAI_API_KEY'
        results.append(check(f'{key_name} configured', key_ok, settings.model))

        if settings.provider == 'openrouter':
            results.append(check('Free test model', settings.model == 'openrouter/free' or ':free' in settings.model,
                                 settings.model))

        results.append(check('Voice output enabled', settings.enable_voice_output,
                             f'rate={settings.voice_rate}, volume={settings.voice_volume}'))
        results.append(check('Microphone input', True, 'not installed by design'))
        results.append(check('Database folder writable',
                             os.access(settings.db_path.parent, os.W_OK) if settings.db_path.parent.exists() else True,
                             str(settings.db_path)))
        roots = [str(p) for p in settings.allowed_file_roots if p.exists()]
        results.append(check('Local roots', bool(roots), '; '.join(roots) or 'none'))
    except Exception as exc:
        results.append(check('JARVIS config', False, str(exc)))

    print('\nJARVIS OMEGA:', 'READY' if all(results) else 'NEEDS ATTENTION')


if __name__ == '__main__':
    main()
