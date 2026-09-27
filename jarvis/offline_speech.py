"""Optional local Vosk recognition. Explicit model path; no downloads or cloud fallback."""
from __future__ import annotations

import json
from pathlib import Path
import threading

_model = None
_model_path = None
_model_lock = threading.Lock()


def transcribe_vosk(data: bytes, sample_rate: int, model_path: str) -> str:
    global _model, _model_path
    if not model_path.strip():
        raise RuntimeError('Set VOSK_MODEL_PATH to an extracted local speech model folder.')
    path = Path(model_path).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError('VOSK_MODEL_PATH does not point to an existing model folder.')
    if sample_rate <= 0 or len(data) % 2:
        raise ValueError('Recognition requires mono 16-bit PCM with a positive sample rate.')
    try:
        import vosk
    except ImportError as exc:
        raise RuntimeError('Install optional offline speech: python -m pip install -r requirements-offline-voice.txt') from exc
    model = get_vosk_model(str(path))
    recognizer = vosk.KaldiRecognizer(model, sample_rate)
    parts = []
    for offset in range(0, len(data), 8000):
        if recognizer.AcceptWaveform(data[offset:offset + 8000]):
            parts.append(json.loads(recognizer.Result()).get('text', ''))
    parts.append(json.loads(recognizer.FinalResult()).get('text', ''))
    return ' '.join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def get_vosk_model(model_path: str):
    """Share one loaded acoustic model; each stream owns its recognizer."""
    global _model, _model_path
    import vosk
    path = str(Path(model_path).expanduser().resolve())
    with _model_lock:
        if _model is None or _model_path != path:
            candidate = vosk.Model(path)
            _model, _model_path = candidate, path
        return _model
