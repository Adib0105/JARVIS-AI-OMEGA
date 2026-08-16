import json
import sys
import types
import unittest
from unittest.mock import patch

from jarvis.agent.verification import VerificationEngine
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.browser import BrowserAgent
from jarvis.computer_use.targets import UITarget, choose_target, target_score
from jarvis.computer_use.windows_ui import BackendStatus


class FakeBackend:
    def __init__(self, targets=None, focus_after=True):
        self.targets = targets or []
        self.focus_after = focus_after

    def status(self):
        return BackendStatus(True, 'fake-uia', 'ready')

    def enumerate_targets(self, **_kwargs):
        return list(self.targets)

    def observe(self, target):
        return target.safe_dict() | {'observed': True, 'exists': True, 'focused': self.focus_after, 'selected': False, 'value': None}

    def click(self, target):
        return self.observe(target)

    def focus(self, target):
        return self.observe(target)


class V7ComputerUseTests(unittest.TestCase):
    def setUp(self):
        self.downloads = UITarget(
            name='Downloads', control_type='TreeItem', window_title='File Explorer',
            left=10, top=20, right=100, bottom=50,
        )
        self.documents = UITarget(
            name='Documents', control_type='TreeItem', window_title='File Explorer',
            left=10, top=60, right=100, bottom=90,
        )

    def test_exact_semantic_target_scores_high(self):
        self.assertGreaterEqual(target_score('Downloads', self.downloads), 0.9)
        match = choose_target('Downloads', [self.downloads, self.documents], threshold=0.82)
        self.assertTrue(match.resolved)
        self.assertEqual(match.target.name, 'Downloads')

    def test_low_confidence_target_is_rejected_not_guessed(self):
        match = choose_target('Delete everything', [self.downloads, self.documents], threshold=0.82)
        self.assertFalse(match.resolved)
        self.assertIn('below threshold', match.reason)

    def test_ambiguous_target_is_rejected(self):
        one = UITarget('Save', 'Button', 'Editor', left=1, top=1, right=2, bottom=2)
        two = UITarget('Save', 'Button', 'Editor', automation_id='secondary', left=3, top=3, right=4, bottom=4)
        match = choose_target('Save', [one, two], threshold=0.82)
        self.assertFalse(match.resolved)
        self.assertIn('ambiguous', match.reason.lower())

    def test_semantic_click_returns_observation_evidence(self):
        engine = ComputerActionEngine(FakeBackend([self.downloads]), confidence_threshold=0.82)
        result = engine.semantic_click('Downloads', window_hint='File Explorer')
        self.assertTrue(result['ok'])
        self.assertEqual(result['verification']['status'], 'VERIFIED')
        self.assertTrue(result['verification']['verified'])

    def test_semantic_type_can_be_partial_when_value_readback_unavailable(self):
        engine = ComputerActionEngine(FakeBackend([self.downloads]), confidence_threshold=0.82)
        fake_pyautogui = types.SimpleNamespace(write=lambda *_args, **_kwargs: None)
        with patch.dict(sys.modules, {'pyautogui': fake_pyautogui}):
            result = engine.semantic_type('Downloads', 'hello', window_hint='File Explorer')
        self.assertTrue(result['ok'])
        self.assertEqual(result['verification']['status'], 'PARTIAL')
        self.assertFalse(result['verification']['verified'])

    def test_verifier_respects_explicit_partial_evidence(self):
        event = {
            'name': 'browser_agent_open',
            'output': json.dumps({
                'ok': True,
                'verification': {'status': 'PARTIAL', 'verified': False, 'evidence': {'browser_process_detected': True}},
            }),
        }
        check = VerificationEngine().verify_tool_event(event)
        self.assertEqual(check['status'], 'PARTIAL')
        self.assertFalse(check['verified'])

    def test_browser_read_marks_page_content_untrusted(self):
        with patch('jarvis.computer_use.browser.read_web_page', return_value={'title': 'Example', 'content': 'hello'}):
            result = BrowserAgent.read('https://example.com', 1000)
        self.assertTrue(result['ok'])
        self.assertTrue(result['untrusted_content'])
        self.assertEqual(result['verification']['status'], 'VERIFIED')

    def test_browser_open_rejects_non_http_scheme(self):
        result = BrowserAgent().open('file:///etc/passwd')
        self.assertFalse(result['ok'])
        self.assertIn('HTTP/HTTPS', result['error'])


if __name__ == '__main__':
    unittest.main()
