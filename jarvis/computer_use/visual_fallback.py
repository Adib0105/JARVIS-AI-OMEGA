from __future__ import annotations

import importlib.util
import shutil
from dataclasses import asdict, dataclass

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
        detail = f'Pillow.ImageGrab={pillow}; pytesseract={pytesseract_pkg}; tesseract={bool(tesseract)}'
        return VisualFallbackStatus(available, 'pytesseract', detail)

    @staticmethod
    def targets_from_rows(rows: list[dict]) -> list[UITarget]:
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
                left = int(row.get('left', 0)); top = int(row.get('top', 0))
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

        image = ImageGrab.grab()
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        rows = []
        count = len(data.get('text', []))
        for index in range(count):
            rows.append({key: values[index] for key, values in data.items() if isinstance(values, list) and index < len(values)})
        targets = self.targets_from_rows(rows)
        match = choose_target(label, targets, threshold=threshold, ambiguity_margin=0.10)
        if match.target is None:
            return TargetMatch(None, match.confidence, f'OCR fallback: {match.reason}', match.alternatives)
        return TargetMatch(match.target, match.confidence, 'Target resolved by local OCR fallback.', match.alternatives)
