import unittest

from jarvis.v10_runtime import AgentState, V10Runtime, V10_CAPABILITIES


class V10RuntimeTests(unittest.TestCase):
    def test_master_capabilities_are_registered(self):
        for key in ('live_companion','barge_in','screen_awareness','computer_use','memory','missions','self_development','audit'):
            self.assertIn(key, V10_CAPABILITIES)

    def test_privacy_cancels_current_work(self):
        runtime = V10Runtime(); runtime.set_privacy(True)
        self.assertTrue(runtime.cancelled); self.assertTrue(runtime.snapshot().privacy_mode)

    def test_emergency_stop_blocks_transitions_until_resumed(self):
        runtime = V10Runtime(); runtime.emergency_stop(); runtime.transition(AgentState.EXECUTING)
        self.assertEqual(runtime.snapshot().state, AgentState.STOPPED)
        runtime.resume_after_stop(); runtime.transition(AgentState.THINKING)
        self.assertEqual(runtime.snapshot().state, AgentState.THINKING)

    def test_snapshot_is_copy(self):
        runtime = V10Runtime(); snap = runtime.snapshot(); snap.state = AgentState.ERROR
        self.assertEqual(runtime.snapshot().state, AgentState.IDLE)


if __name__ == '__main__':
    unittest.main()
