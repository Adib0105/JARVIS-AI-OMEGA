import unittest
from unittest.mock import patch

from jarvis.computer_use.visual_fallback import VisualTargetBackend


class V75VisualFallbackTests(unittest.TestCase):
    def test_rows_become_visible_ocr_targets_only_above_confidence_floor(self):
        rows = [
            {'text': 'Submit', 'conf': '92', 'left': 10, 'top': 20, 'width': 80, 'height': 30},
            {'text': 'noise', 'conf': '20', 'left': 1, 'top': 1, 'width': 5, 'height': 5},
            {'text': '', 'conf': '99', 'left': 1, 'top': 1, 'width': 5, 'height': 5},
        ]
        targets = VisualTargetBackend.targets_from_rows(rows)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].name, 'Submit')
        self.assertEqual(targets[0].control_type, 'OCRText')
        self.assertEqual(targets[0].center, (50, 35))

    def test_virtual_desktop_offset_is_applied_to_ocr_coordinates(self):
        rows = [
            {'text': 'Left monitor button', 'conf': '95', 'left': 100, 'top': 40, 'width': 80, 'height': 20},
        ]
        targets = VisualTargetBackend.targets_from_rows(rows, offset_x=-1920, offset_y=-100)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].safe_dict()['bounds'], [-1820, -60, -1740, -40])
        self.assertEqual(targets[0].center, (-1780, -50))

    def test_missing_ocr_runtime_returns_no_target_instead_of_guessing(self):
        backend = VisualTargetBackend()
        fake = type('S', (), {'available': False, 'backend': 'none', 'detail': 'not installed'})()
        with patch.object(backend, 'status', return_value=fake):
            match = backend.resolve('Delete account')
        self.assertIsNone(match.target)
        self.assertEqual(match.confidence, 0.0)
        self.assertIn('unavailable', match.reason.lower())

    def test_ambiguous_ocr_labels_are_rejected_by_existing_confidence_policy(self):
        # Test the deterministic target scoring path without invoking OCR.
        rows = [
            {'text': 'Save', 'conf': '95', 'left': 10, 'top': 10, 'width': 80, 'height': 20},
            {'text': 'Save', 'conf': '96', 'left': 200, 'top': 10, 'width': 80, 'height': 20},
        ]
        from jarvis.computer_use.targets import choose_target
        match = choose_target('Save', VisualTargetBackend.targets_from_rows(rows), threshold=0.88, ambiguity_margin=0.10)
        self.assertIsNone(match.target)
        self.assertIn('ambiguous', match.reason.lower())


if __name__ == '__main__':
    unittest.main()