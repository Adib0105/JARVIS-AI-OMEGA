from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

from .config import ROOT


SCREEN_DIR = ROOT / 'data' / 'screens'


def capture_screen() -> Path:
    """Capture the current desktop to a local PNG file. Caller must obtain user approval first."""
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = SCREEN_DIR / f'screen-{stamp}.png'
    image = ImageGrab.grab(all_screens=True)
    image.save(target, format='PNG', optimize=True)
    return target


def image_data_url(image_path: str | Path, max_bytes: int = 12_000_000) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('Only PNG, JPEG, and WEBP images are supported.')
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError('Image is too large for vision analysis.')
    mime = 'image/png'
    if path.suffix.lower() in {'.jpg', '.jpeg'}:
        mime = 'image/jpeg'
    elif path.suffix.lower() == '.webp':
        mime = 'image/webp'
    encoded = base64.b64encode(data).decode('ascii')
    return f'data:{mime};base64,{encoded}'
