from __future__ import annotations

import importlib.util
import shutil
from dataclasses import asdict, dataclass

from .display_context import get_display_context
from .targets import TargetMatch, UITarget, choose_target


@dataclass(frozen=True)
class VisualFallbackStatus:
    available: bool
    backend: str
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


class VisualTargetBackend:
    """Optional local OCR fallback after semantic UIA fails.

    No dependency is installed automatically. If pytesseract/Tesseract or Pillow
    ImageGrab are unavailable, this backend returns unavailable and the caller must
    ask the user rather than guessing coordinates.
    """

    def status(self) -> VisualFallbackStatus:
        pillow = importlib.util.find_spec('PIL.ImageGrab') is not None
        pytesseract_pkg = importlib.util.find_spec('pytesseract') is not None
        tesseract = shutil.which('tesseract')
        available = bool(pillow and pytesseract_pkg and tesseract)
        display = get_display_context()
        detail = (
            f'Pillow.ImageGrab={pillow}; pytesseract={pytesseract_pkg}; '
            f'tesseract={bool(tesseract)}; monitors={display.monitor_count if display.available else "unknown"}'
        )
        return VisualFallbackStatus(available, 'pytesseract', detail)

    @staticmethod
    def targets_from_rows(rows: list[dict], *, offset_x: int = 0, offset_y: int = 0) -> list[UITarget]:
        targets: list[UITarget] = []
        for row in rows:
            text = str(row.get('text') or '').strip()
            try:
                confidence = float(row.get('conf', -1))
            except (TypeError, ValueError):
                confidence = -1
            if not text or confidence < 40:
                continue
            try:
                left = int(row.get('left', 0)) + int(offset_x)
                top = int(row.get('top', 0)) + int(offset_y)
                width = int(row.get('width', 0)); height = int(row.get('height', 0))
            except (TypeError, ValueError):
                continue
            if width <= 0 or height <= 0:
                continue
            targets.append(UITarget(
                name=text,
                control_type='OCRText',
                window_title='SCREEN_OCR',
                automation_id='',
                left=left, top=top, right=left + width, bottom=top + height,
                enabled=True, visible=True, backend_ref=None,
            ))
        return targets

    def resolve(self, label: str, *, threshold: float = 0.88) -> TargetMatch:
        status = self.status()
        if not status.available:
            return TargetMatch(None, 0.0, f'Visual/OCR fallback unavailable: {status.detail}', ())
        from PIL import ImageGrab
        import pytesseract
        from pytesseract import Output

        display = get_display_context()
        grab_kwargs = {'all_screens': True} if display.available else {}
        try:
            image = ImageGrab.grab(**grab_kwargs)
        except TypeError:
            # Older/non-Windows Pillow backends may not expose all_screens.
            image = ImageGrab.grab()
            display = get_display_context()

        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        rows = []
        count = len(data.get('text', []))
        for index in range(count):
            rows.append({key: values[index] for key, values in data.items() if isinstance(values, list) and index < len(values)})

        # all_screens=True returns an image whose origin is the virtual desktop's
        # top-left. That origin may be negative when a monitor sits left/above primary.
        offset_x = display.virtual_left if display.available else 0
        offset_y = display.virtual_top if display.available else 0
        targets = self.targets_from_rows(rows, offset_x=offset_x, offset_y=offset_y)
        match = choose_target(label, targets, threshold=threshold, ambiguity_margin=0.10)
        if match.target is None:
            return TargetMatch(None, match.confidence, f'OCR fallback: {match.reason}', match.alternatives)
        return TargetMatch(match.target, match.confidence, 'Target resolved by local OCR fallback.', match.alternatives)