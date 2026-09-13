"""Windows release gate: synthesize real audio without using speakers or keys."""
from pathlib import Path
import tempfile
import wave


def main():
    from .speech_worker import speak_windows_sapi
    with tempfile.TemporaryDirectory(prefix='jarvis audio test ') as folder:
        root = Path(folder)
        text = root / 'input with spaces.txt'
        text.write_text('Hello boss. Friday is ready.', encoding='utf-8')
        output = root / 'speech.wav'
        speak_windows_sapi(text, 1.0, output)
        with wave.open(str(output), 'rb') as audio:
            frames = audio.readframes(audio.getnframes())
            if audio.getnframes() < 1000 or not any(frames):
                raise RuntimeError('Windows speech produced empty or silent audio.')
    return 0
