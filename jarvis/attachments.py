from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageGrab

from .config import ROOT, settings

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
ATTACHMENT_DIR = ROOT / 'data' / 'attachments'


def validate_image(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    if p.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError('Supported image types: PNG, JPG, JPEG, WEBP.')
    max_bytes = max(1, settings.max_image_mb) * 1024 * 1024
    if p.stat().st_size > max_bytes:
        raise ValueError(f'Image is larger than the configured {settings.max_image_mb} MB limit.')
    try:
        with Image.open(p) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f'Invalid or unreadable image: {p.name}') from exc
    return p


def image_info(path: str | Path) -> dict:
    p = validate_image(path)
    with Image.open(p) as image:
        width, height = image.size
        mode = image.mode
    return {
        'path': str(p),
        'name': p.name,
        'width': width,
        'height': height,
        'mode': mode,
        'size_mb': round(p.stat().st_size / (1024 * 1024), 2),
    }


def image_data_url(path: str | Path) -> str:
    """Resize/compress an image in memory and return a provider-ready data URL."""
    p = validate_image(path)
    with Image.open(p) as source:
        image = source.convert('RGB')
        max_dim = max(512, settings.image_max_dimension)
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        image.save(
            buf,
            format='JPEG',
            quality=max(55, min(settings.image_jpeg_quality, 95)),
            optimize=True,
        )
    encoded = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


def save_clipboard_image() -> Path:
    """Save an image currently present in the Windows clipboard to a local PNG."""
    content = ImageGrab.grabclipboard()
    if content is None:
        raise RuntimeError('Clipboard me image nahi mili.')

    if isinstance(content, list):
        image_candidates = [
            Path(item) for item in content
            if isinstance(item, str) and Path(item).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]
        if image_candidates:
            return validate_image(image_candidates[0])
        raise RuntimeError('Clipboard me supported image nahi mili.')

    if not isinstance(content, Image.Image):
        raise RuntimeError('Clipboard content image format me nahi hai.')

    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = ATTACHMENT_DIR / f'clipboard-{stamp}.png'
    content.save(target, format='PNG')
    return validate_image(target)


def normalize_image_paths(paths: list[str | Path]) -> list[Path]:
    if not paths:
        raise ValueError('At least one image is required.')
    if len(paths) > settings.max_image_attachments:
        raise ValueError(f'Maximum {settings.max_image_attachments} images can be attached at once.')
    return [validate_image(path) for path in paths]
