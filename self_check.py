from __future__ import annotations

import os
import platform
import sys


def check(label: str, ok: bool, detail: str = '') -> bool:
    tag = 'PASS' if ok else 'FAIL'
    print(f'[{tag}] {label}' + (f' - {detail}' if detail else ''))
    return ok


def optional(label: str, ok: bool, detail: str = '') -> None:
    tag = 'PASS' if ok else 'INFO'
    print(f'[{tag}] {label}' + (f' - {detail}' if detail else ''))


def main() -> None:
    results = []
    results.append(check('Python >= 3.10', sys.version_info >= (3, 10), platform.python_version()))

    required_imports = [
        ('OpenAI-compatible SDK', 'openai'),
        ('Rich terminal UI', 'rich'),
        ('Free public web search', 'ddgs'),
        ('System telemetry', 'psutil'),
        ('PDF intelligence', 'pypdf'),
        ('DOCX intelligence', 'docx'),
        ('Excel intelligence', 'openpyxl'),
    ]
    for label, module in required_imports:
        try:
            imported = __import__(module)
            results.append(check(label, True, getattr(imported, '__version__', 'installed')))
        except Exception as exc:
            results.append(check(label, False, str(exc)))

    try:
        from PIL import Image, ImageGrab, ImageTk
        _ = (Image, ImageGrab, ImageTk)
        results.append(check('V6 image upload + screen vision', True, 'Pillow installed'))
    except Exception as exc:
        results.append(check('V6 image upload + screen vision', False, str(exc)))

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
        results.append(check('Animated ARC desktop GUI', True, f'Tk {tkinter.TkVersion}'))
    except Exception as exc:
        results.append(check('Animated ARC desktop GUI', False, str(exc)))

    # Optional Windows modules: text chat remains usable if these are missing.
    try:
        import pyautogui
        optional('Desktop keyboard/mouse automation', True, getattr(pyautogui, '__version__', 'installed'))
    except Exception as exc:
        optional('Desktop keyboard/mouse automation', False, f'optional: {exc}')
    try:
        import sounddevice
        import speech_recognition
        optional('Push-to-talk / wake-word microphone', True, 'sounddevice + SpeechRecognition installed')
    except Exception as exc:
        optional('Push-to-talk / wake-word microphone', False, f'optional: {exc}')

    try:
        from jarvis import __version__
        from jarvis.config import settings

        results.append(check('JARVIS version', __version__ == settings.app_version == '6.0.0', __version__))
        provider_ok = settings.provider in {'openrouter', 'openai'}
        results.append(check('AI provider', provider_ok, settings.provider))

        placeholder = 'put_your_openrouter_key_here' if settings.provider == 'openrouter' else 'put_your_api_key_here'
        key_ok = bool(settings.api_key and settings.api_key != placeholder)
        key_name = 'OPENROUTER_API_KEY' if settings.provider == 'openrouter' else 'OPENAI_API_KEY'
        results.append(check(f'{key_name} configured', key_ok, settings.model))

        if settings.provider == 'openrouter':
            results.append(check('Free test model', settings.model == 'openrouter/free' or ':free' in settings.model, settings.model))

        results.append(check('Public web tools', settings.enable_public_web_tools, 'DDGS metasearch'))
        results.append(check('Desktop automation config', settings.enable_desktop_automation, 'approval-gated'))
        results.append(check('Document intelligence config', settings.enable_document_intelligence, 'PDF/DOCX/XLSX/CSV'))
        results.append(check('Coding workspace config', settings.enable_coding_tools, 'safe writes + unittest'))
        results.append(check('Mission planner config', settings.mission_max_steps >= 1, f'max steps={settings.mission_max_steps}'))
        results.append(check('Image attachments', settings.max_image_attachments >= 1, f'max={settings.max_image_attachments}'))
        results.append(check('AI timeout', settings.ai_timeout_seconds > 0, f'{settings.ai_timeout_seconds}s'))
        results.append(check('Vision timeout', settings.vision_timeout_seconds > 0, f'{settings.vision_timeout_seconds}s'))

        voice_detail = (
            f'engine={settings.voice_engine}, hindi={settings.voice_hindi}, '
            f'hinglish={settings.voice_hinglish}, pitch={settings.edge_voice_pitch}, rate={settings.edge_voice_rate}'
        )
        results.append(check('Voice output enabled', settings.enable_voice_output, voice_detail))
        optional('Microphone configured', settings.enable_mic_input, f'wake default={settings.enable_wake_word}, phrase={settings.wake_word}')
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

    print('\nJARVIS OMEGA V6:', 'READY' if all(results) else 'NEEDS ATTENTION')


if __name__ == '__main__':
    main()
