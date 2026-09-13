"""Install the official small Indian English Vosk data model without shell code."""
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import time
import zipfile
from urllib.request import urlopen

MODEL_NAME = 'vosk-model-small-en-in-0.4'
MODEL_URL = 'https://alphacephei.com/vosk/models/' + MODEL_NAME + '.zip'


def model_valid(path):
    root = Path(path)
    return all((root / item).is_file() for item in ('am/final.mdl', 'conf/model.conf'))


def install_model(parent, progress=lambda text: None):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / MODEL_NAME
    if model_valid(destination):
        return destination
    if destination.exists():
        raise RuntimeError('Incomplete model folder exists. Choose a valid model folder or remove the incomplete download first.')
    with tempfile.TemporaryDirectory(prefix='wake-download-', dir=parent) as tmp:
        archive = Path(tmp) / 'model.zip'
        started = time.monotonic()
        total = 0
        with urlopen(MODEL_URL, timeout=20) as response, archive.open('wb') as out:
            while True:
                data = response.read(128 * 1024)
                if not data:
                    break
                total += len(data)
                if total > 80 * 1024 * 1024 or time.monotonic() - started > 600:
                    raise RuntimeError('Model download exceeded its size/time limit. Retry with a stable connection.')
                out.write(data)
                progress(f'Downloading wake model: {total // (1024 * 1024)} MB')
        extracted = Path(tmp) / 'extracted'
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 250 * 1024 * 1024:
                raise RuntimeError('Model archive exceeds extraction limits.')
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                        or ':' in entry.filename or not path.parts or path.parts[0] != MODEL_NAME
                        or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    raise RuntimeError('Model archive contains an unsafe path.')
            bundle.extractall(extracted)
        source = extracted / MODEL_NAME
        if not model_valid(source):
            raise RuntimeError('Downloaded model is incomplete; no model was installed.')
        shutil.move(str(source), str(destination))
    return destination
