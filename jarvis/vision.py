from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageGrab

from .config import ROOT, settings


SCREEN_DIR = ROOT / 'data' / 'screens'


def capture_screen() -> Path:
    """Capture, resize and compress the desktop. Caller must obtain approval first."""
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = SCREEN_DIR / f'screen-{stamp}.jpg'

    image = ImageGrab.grab(all_screens=True).convert('RGB')
    max_size = (
        max(640, settings.vision_max_width),
        max(480, settings.vision_max_height),
    )
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    quality = max(50, min(settings.vision_jpeg_quality, 95))
    image.save(target, format='JPEG', quality=quality, optimize=True)
    return target


def image_data_url(image_path: str | Path, max_bytes: int = 8_000_000) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('Only PNG, JPEG, and WEBP images are supported.')
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError('Image is too large for vision analysis. Reduce VISION_MAX_WIDTH/HEIGHT.')
    mime = 'image/png'
    if path.suffix.lower() in {'.jpg', '.jpeg'}:
        mime = 'image/jpeg'
    elif path.suffix.lower() == '.webp':
        mime = 'image/webp'
    encoded = base64.b64encode(data).decode('ascii')
    return f'data:{mime};base64,{encoded}'
