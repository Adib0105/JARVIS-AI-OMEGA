import unittest
from datetime import datetime

from jarvis.v10_companion import CompanionController, CompanionMode, smart_greeting
from jarvis.v10_performance import PerformanceMode, choose_profile
from jarvis.v10_runtime import AgentState, V10Runtime
from jarvis.v10_security import classify_action


class V10FoundationTests(unittest.TestCase):
    def test_emergency_stop_blocks_transition_until_resume(self):
        rt = V10Runtime()
        rt.emergency_stop()
        rt.transition(AgentState.LISTENING)
        self.assertEqual(rt.snapshot().state, AgentState.STOPPED)
        rt.resume_after_stop()
        rt.transition(AgentState.LISTENING)
        self.assertEqual(rt.snapshot().state, AgentState.LISTENING)

    def test_privacy_cancels_current_work(self):
        rt = V10Runtime()
        rt.set_privacy(True)
        self.assertTrue(rt.snapshot().privacy_mode)
        self.assertTrue(rt.cancelled)

    def test_companion_privacy_disables_listening(self):
        controller = CompanionController()
        controller.set_mode(CompanionMode.PRIVACY)
        self.assertFalse(controller.can_listen())
        controller.set_mode(CompanionMode.ACTIVE)

    def test_greeting_by_time(self):
        self.assertEqual(smart_greeting(datetime(2026, 1, 1, 8), 'Adib'), 'Good morning, Adib.')
        self.assertEqual(smart_greeting(datetime(2026, 1, 1, 19), 'Adib'), 'Good evening, Adib.')

    def test_sensitive_action_requires_explicit_request(self):
        blocked = classify_action('delete')
        allowed = classify_action('delete', explicit_user_request=True)
        self.assertFalse(blocked.allowed)
        self.assertTrue(blocked.requires_confirmation)
        self.assertTrue(allowed.allowed)
        self.assertTrue(allowed.requires_confirmation)

    def test_low_memory_downgrades_performance(self):
        self.assertEqual(choose_profile('performance', memory_gb=3).mode, PerformanceMode.ECO)
        self.assertEqual(choose_profile('performance', memory_gb=5).mode, PerformanceMode.BALANCED)


if __name__ == '__main__':
    unittest.main()
