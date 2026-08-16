from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

from .attachments import image_data_url
from .config import ROOT

SCREEN_DIR = ROOT / 'data' / 'screens'


def capture_screen() -> Path:
    """Capture the current desktop to a local PNG. Caller must obtain user approval first."""
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = SCREEN_DIR / f'screen-{stamp}.png'
    image = ImageGrab.grab(all_screens=True)
    image.save(target, format='PNG', optimize=True)
    return target


__all__ = ['capture_screen', 'image_data_url']
