"""Local, read-only voice checks; never record audio or contact an AI service."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
from .config import settings
from .voice_profiles import profile_overrides


def diagnose_voice(profile: str = 'configured', config=None) -> dict:
    config = config or settings
    overrides = profile_overrides(profile)
    engine = overrides.get('VOICE_ENGINE', config.voice_engine)
    stt = config.speech_engine
    checks = []
    def add(name, ok, detail):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
    def installed(name):
        try:
            return importlib.util.find_spec(name) is not None
        except (ValueError, ImportError):
            return False
    add('Speech output', config.enable_voice_output, 'ENABLE_VOICE_OUTPUT controls spoken replies.')
    package = {'edge': 'edge_tts', 'openai': 'openai', 'pyttsx3': 'pyttsx3'}.get(engine)
    add('Voice engine package', package and installed(package), f'Selected engine: {engine}')
    if engine == 'openai':
        add('OpenAI key', bool(config.openai_api_key.strip()), 'Key present/missing only; API credit and access are not tested.')
    if engine in {'edge', 'openai'}:
        add('Audio player', os.name == 'nt' or bool(shutil.which('mpv') or shutil.which('ffplay')), 'Windows native playback; otherwise install mpv or ffplay.')
    add('Microphone enabled', config.enable_mic_input, 'ENABLE_MIC_INPUT controls recording.')
    add('Capture package', installed('sounddevice'), 'Install requirements-windows.txt for sounddevice.')
    devices = []
    try:
        import sounddevice as sd
        devices = [{'id': index, 'name': str(device['name']), 'channels': int(device['max_input_channels'])}
                   for index, device in enumerate(sd.query_devices()) if device['max_input_channels'] > 0]
        add('Input devices', bool(devices), 'Device enumeration only; microphone was not opened.')
    except Exception:
        add('Input devices', False, 'Audio device enumeration unavailable; check sounddevice/PortAudio and drivers.')
    if stt == 'vosk':
        add('Offline recognizer', installed('vosk'), 'Install requirements-offline-voice.txt.')
        add('Offline model folder', bool(config.vosk_model_path) and Path(config.vosk_model_path).expanduser().is_dir(), 'Set VOSK_MODEL_PATH to an extracted language model. Model loading is not tested.')
    else:
        add('Online recognizer', stt == 'google' and installed('speech_recognition'), 'Google recognition needs internet; availability is not tested.')
    return {'profile': profile, 'voice_engine': engine, 'speech_engine': stt,
            'speech_output_uses_network': engine in {'edge', 'openai'},
            'recognition_uses_network': stt == 'google',
            'configured_input_device': config.mic_device or 'system default', 'input_devices': devices,
            'checks': checks, 'note': 'Local configuration checks only. No audio recording, network calls or credentials are included.'}


def main() -> None:
    import json
    from .voice_profiles import load_profile
    print(json.dumps(diagnose_voice(load_profile(settings.db_path.parent / 'voice_preferences.json')), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
