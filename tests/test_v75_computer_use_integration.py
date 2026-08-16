import sys
import types
import unittest
from unittest.mock import patch

from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.targets import TargetMatch, UITarget
from jarvis.computer_use.visual_fallback import VisualFallbackStatus
from jarvis.computer_use.windows_ui import BackendStatus


class EmptyUIA:
    def status(self):
        return BackendStatus(False, 'fake-uia', 'unavailable')

    def enumerate_targets(self, **_kwargs):
        return []


class AmbiguousUIA:
    def __init__(self):
        self.targets = [
            UITarget('Save', 'Button', 'Editor', left=1, top=1, right=20, bottom=20),
            UITarget('Save', 'Button', 'Editor', left=30, top=1, right=50, bottom=20),
        ]

    def status(self):
        return BackendStatus(True, 'fake-uia', 'ready')

    def enumerate_targets(self, **_kwargs):
        return list(self.targets)


class FakeVisual:
    def __init__(self, target=None):
        self.target = target
        self.calls = 0

    def status(self):
        return VisualFallbackStatus(True, 'fake-ocr', 'ready')

    def resolve(self, label, *, threshold=0.88):
        self.calls += 1
        if self.target is None:
            return TargetMatch(None, 0.2, 'OCR no match', ())
        return TargetMatch(self.target, 0.95, 'Target resolved by local OCR fallback.', ())


class V75ComputerUseIntegrationTests(unittest.TestCase):
    def test_ocr_fallback_click_is_partial_not_false_verified(self):
        ocr = UITarget(
            'Submit', 'OCRText', 'SCREEN_OCR',
            left=100, top=100, right=200, bottom=140,
        )
        visual = FakeVisual(ocr)
        engine = ComputerActionEngine(EmptyUIA(), visual_backend=visual)
        fake_pyautogui = types.SimpleNamespace(click=lambda **_kwargs: None, write=lambda *_args, **_kwargs: None)
        with patch.dict(sys.modules, {'pyautogui': fake_pyautogui}):
            result = engine.semantic_click('Submit')
        self.assertTrue(result['ok'])
        self.assertEqual(result['resolution_backend'], 'local-ocr')
        self.assertEqual(result['verification']['status'], 'PARTIAL')
        self.assertFalse(result['verification']['verified'])
        self.assertEqual(visual.calls, 1)

    def test_ambiguous_uia_result_never_falls_through_to_ocr_guess(self):
        visual = FakeVisual(UITarget('Save', 'OCRText', 'SCREEN_OCR', left=1, top=1, right=20, bottom=20))
        engine = ComputerActionEngine(AmbiguousUIA(), visual_backend=visual)
        result = engine.semantic_click('Save')
        self.assertFalse(result['ok'])
        self.assertIn('ambiguous', result['reason'].lower())
        self.assertEqual(visual.calls, 0)

    def test_no_uia_and_no_ocr_match_stops_without_coordinate_guess(self):
        visual = FakeVisual(None)
        engine = ComputerActionEngine(EmptyUIA(), visual_backend=visual)
        result = engine.semantic_click('Dangerous unknown control')
        self.assertFalse(result['ok'])
        self.assertIn('will not guess', result['error'])
        self.assertEqual(visual.calls, 1)


if __name__ == '__main__':
    unittest.main()
