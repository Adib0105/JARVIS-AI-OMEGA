import json
import tempfile
import unittest
from pathlib import Path

from jarvis.agent.mission import MissionStatus, StepStatus
from jarvis.agent.mission_store import MissionStore
from jarvis.agent.orchestrator import MissionControl, MissionOrchestrator


class FakeTools:
    def __init__(self):
        self.events = []

    def clear_events(self):
        self.events = []

    def drain_events(self):
        output = list(self.events)
        self.events = []
        return output


class FakeCore:
    session_id = 'test-session'
    last_provider_used = 'fake'

    def __init__(self, plan, turns, replan=None):
        self._plan = list(plan)
        self._turns = list(turns)
        self._replan = replan if replan is not None else []
        self.tools = FakeTools()
        self.last_plan = list(plan)

    def plan_mission(self, _goal):
        return list(self._plan)

    def chat(self, _prompt):
        if not self._turns:
            raise RuntimeError('No fake turn configured')
        item = self._turns.pop(0)
        if isinstance(item, BaseException):
            raise item
        self.tools.events = list(item.get('events', []))
        return item.get('text', 'ok')

    def _one_shot_text(self, _instruction, _prompt, _kind='mission'):
        return json.dumps(self._replan)

    @staticmethod
    def _extract_plan(raw, max_steps):
        parsed = json.loads(raw)
        return [str(item).strip() for item in parsed if str(item).strip()][:max_steps]


def event(name, result=None, error=None, args=None):
    payload = {'ok': error is None}
    if error is None:
        payload['result'] = result
    else:
        payload['error'] = error
    return {
        'name': name,
        'args': args or {},
        'output': json.dumps(payload),
    }


class V7MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MissionStore(Path(self.temp.name) / 'jarvis-test.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_successful_reasoning_mission_is_persisted_and_verified(self):
        core = FakeCore(['Analyze'], [{'text': 'Analysis complete', 'events': []}])
        orchestrator = MissionOrchestrator(core, self.store)
        mission = orchestrator.run('Analyze something')
        self.assertEqual(mission.status, MissionStatus.COMPLETED)
        self.assertTrue(mission.final_verification.verified)
        loaded = self.store.get(mission.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, MissionStatus.COMPLETED)
        self.assertTrue(self.store.events(mission.id))

    def test_unobserved_desktop_action_is_partial_not_false_verified(self):
        core = FakeCore([
            'Open app'
        ], [{
            'text': 'Requested app launch',
            'events': [event('open_app', 'Opened notepad.')],
        }])
        mission = MissionOrchestrator(core, self.store).run('Open Notepad')
        self.assertEqual(mission.status, MissionStatus.COMPLETED)
        self.assertFalse(mission.final_verification.verified)
        self.assertEqual(mission.final_verification.status, 'PARTIAL')
        self.assertIn('open_app', mission.final_verification.unverified_actions)
        self.assertIn('not claiming full verified success', mission.final_report)

    def test_permission_denial_stops_without_retry_or_replan(self):
        core = FakeCore([
            'Write file'
        ], [{
            'text': 'Could not write',
            'events': [event('write_local_text_file', error='Action was not approved by user.')],
        }], replan=['Should never run'])
        mission = MissionOrchestrator(core, self.store).run('Write file')
        self.assertEqual(mission.status, MissionStatus.FAILED)
        self.assertEqual(mission.retry_count, 0)
        self.assertEqual(mission.recovery_count, 0)
        self.assertIn('permission was denied', mission.last_error.lower())

    def test_transient_timeout_retries_read_only_step(self):
        core = FakeCore(['Fetch'], [TimeoutError('timed out'), {'text': 'Recovered', 'events': []}])
        orchestrator = MissionOrchestrator(core, self.store)
        orchestrator.retry.wait = lambda *_args, **_kwargs: True
        mission = orchestrator.run('Fetch data')
        self.assertEqual(mission.status, MissionStatus.COMPLETED)
        self.assertEqual(mission.retry_count, 1)
        self.assertEqual(mission.plan[0].attempts, 2)

    def test_replan_preserves_failure_history_and_supersedes_old_pending_work(self):
        core = FakeCore(
            ['Fragile step', 'Old remaining step'],
            [
                {'text': 'failed', 'events': [event('search_web', error='tool failed')]},
                {'text': 'alternative succeeded', 'events': []},
            ],
            replan=['Alternative step'],
        )
        mission = MissionOrchestrator(core, self.store).run('Recoverable goal')
        self.assertEqual(mission.status, MissionStatus.COMPLETED)
        self.assertEqual(mission.recovery_count, 1)
        self.assertTrue(mission.plan[0].recovered)
        self.assertEqual(mission.plan[1].status, StepStatus.SUPERSEDED)
        self.assertEqual(mission.plan[-1].status, StepStatus.COMPLETED)
        self.assertTrue(mission.final_verification.verified)

    def test_control_pause_resume_cancel_flags(self):
        control = MissionControl.create()
        self.assertFalse(control.paused)
        self.assertFalse(control.cancelled)
        control.pause()
        self.assertTrue(control.paused)
        control.resume()
        self.assertFalse(control.paused)
        control.cancel()
        self.assertTrue(control.cancelled)
        self.assertFalse(control.paused)


if __name__ == '__main__':
    unittest.main()
