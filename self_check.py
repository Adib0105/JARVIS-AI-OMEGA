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
        import ddgs
        results.append(check('Free public web search', True, getattr(ddgs, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('Free public web search', False, str(exc)))
    try:
        from PIL import Image, ImageGrab, ImageTk
        _ = (Image, ImageGrab, ImageTk)
        results.append(check('V5 image upload + screen vision', True, 'Pillow installed'))
    except Exception as exc:
        results.append(check('V5 image upload + screen vision', False, str(exc)))
    try:
        import edge_tts
        results.append(check('Neural Hindi/Hinglish TTS', True, getattr(edge_tts, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('Neural Hindi/Hinglish TTS', False, str(exc)))
    try:
        import pyttsx3
        results.append(check('Offline TTS fallback', True, getattr(pyttsx3, '__version__', 'installed')))
    except Exception as exc:
        results.append(check('Offline TTS fallback', False, str(exc)))
    try:
        import tkinter
        results.append(check('Desktop GUI', True, f'Tk {tkinter.TkVersion}'))
    except Exception as exc:
        results.append(check('Desktop GUI', False, str(exc)))

    try:
        from jarvis import __version__
        from jarvis.config import settings

        results.append(check('JARVIS version', __version__ == settings.app_version, __version__))
        provider_ok = settings.provider in {'openrouter', 'openai'}
        results.append(check('AI provider', provider_ok, settings.provider))

        placeholder = 'put_your_openrouter_key_here' if settings.provider == 'openrouter' else 'put_your_api_key_here'
        key_ok = bool(settings.api_key and settings.api_key != placeholder)
        key_name = 'OPENROUTER_API_KEY' if settings.provider == 'openrouter' else 'OPENAI_API_KEY'
        results.append(check(f'{key_name} configured', key_ok, settings.model))

        if settings.provider == 'openrouter':
            results.append(check(
                'Free test model',
                settings.model == 'openrouter/free' or ':free' in settings.model,
                settings.model,
            ))

        results.append(check('Custom free web tools', settings.enable_public_web_tools, 'DDGS metasearch'))
        image_detail = (
            f'max={settings.max_image_attachments}, {settings.max_image_mb}MB each, '
            f'{settings.image_max_dimension}px, quality={settings.image_jpeg_quality}'
        )
        results.append(check('Image attachment configuration', settings.max_image_attachments >= 1, image_detail))
        results.append(check('AI timeout configuration', settings.ai_timeout_seconds > 0, f'{settings.ai_timeout_seconds}s'))
        results.append(check('Vision timeout configuration', settings.vision_timeout_seconds > 0, f'{settings.vision_timeout_seconds}s'))

        voice_detail = (
            f'engine={settings.voice_engine}, hindi={settings.voice_hindi}, '
            f'hinglish={settings.voice_hinglish}, pitch={settings.edge_voice_pitch}, rate={settings.edge_voice_rate}'
        )
        results.append(check('Voice output enabled', settings.enable_voice_output, voice_detail))
        results.append(check('Microphone input', True, 'not installed by design'))
        results.append(check(
            'Database folder writable',
            os.access(settings.db_path.parent, os.W_OK) if settings.db_path.parent.exists() else True,
            str(settings.db_path),
        ))
        results.append(check('Export folder configured', True, str(settings.export_dir)))
        roots = [str(p) for p in settings.allowed_file_roots if p.exists()]
        results.append(check('Local roots', bool(roots), '; '.join(roots) or 'none'))
    except Exception as exc:
        results.append(check('JARVIS config', False, str(exc)))

    print('\nJARVIS OMEGA V5:', 'READY' if all(results) else 'NEEDS ATTENTION')


if __name__ == '__main__':
    main()
