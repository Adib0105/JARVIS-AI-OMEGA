"""Named voice preferences. Only a profile name is stored, never API credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

PROFILES = {
    'configured': ('Use .env settings', {}),
    'gentle': ('Gentle female — online Edge', {'VOICE_ENGINE': 'edge', 'EDGE_VOICE_RATE': '-8%', 'EDGE_VOICE_PITCH': '+0Hz', 'VOICE_HINDI': 'hi-IN-SwaraNeural', 'VOICE_HINGLISH': 'en-IN-NeerjaNeural', 'VOICE_ENGLISH': 'en-IN-NeerjaNeural'}),
    'bright': ('Bright female — online Edge', {'VOICE_ENGINE': 'edge', 'EDGE_VOICE_RATE': '+5%', 'EDGE_VOICE_PITCH': '+2Hz', 'VOICE_HINDI': 'hi-IN-SwaraNeural', 'VOICE_HINGLISH': 'en-IN-NeerjaNeural', 'VOICE_ENGLISH': 'en-IN-NeerjaNeural'}),
    'premium': ('Warm female — OpenAI, API charges apply', {'VOICE_ENGINE': 'openai', 'OPENAI_TTS_VOICE': 'coral'}),
    'offline': ('Installed offline voice', {'VOICE_ENGINE': 'pyttsx3'}),
}


def profile_overrides(name: str) -> dict[str, str]:
    if name not in PROFILES:
        raise ValueError('Unknown voice profile. Choose: ' + ', '.join(PROFILES))
    return dict(PROFILES[name][1])


def load_profile(path: Path) -> str:
    try:
        if path.stat().st_size > 4096:
            return 'configured'
        value = json.loads(path.read_text(encoding='utf-8'))
        name = value.get('profile') if isinstance(value, dict) else None
        return name if isinstance(name, str) and name in PROFILES else 'configured'
    except (OSError, ValueError, UnicodeError):
        return 'configured'


def save_profile(path: Path, name: str) -> None:
    profile_overrides(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({'profile': name}, handle)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
