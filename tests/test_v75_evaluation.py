import tempfile
import unittest
from pathlib import Path

from jarvis.agent.mission import Mission, MissionStatus, VerificationResult
from jarvis.agent.mission_store import MissionStore
from jarvis.capability_registry import CapabilityRegistry
from jarvis.evaluation import SelfEvaluationEngine
from jarvis.security.audit import AuditStore


class V75SelfEvaluationTests(unittest.TestCase):
    def _engine(self, path: Path):
        missions = MissionStore(path)
        audit = AuditStore(path)
        engine = SelfEvaluationEngine(
            path,
            mission_store=missions,
            audit_store=audit,
            capability_registry=CapabilityRegistry(),
        )
        return engine, missions, audit

    @staticmethod
    def _save_terminal(store: MissionStore, *, goal: str, status: MissionStatus, verified: bool, retry=0, recovery=0):
        mission = Mission(goal=goal, session_id='S-TEST')
        mission.status = status
        mission.retry_count = retry
        mission.recovery_count = recovery
        mission.final_verification = VerificationResult(
            verified=verified,
            status='VERIFIED' if verified else ('FAILED' if status == MissionStatus.FAILED else 'PARTIAL'),
            summary='test evidence',
        )
        store.save(mission)
        return mission

    def test_measured_rates_come_from_persisted_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jarvis.db'
            engine, missions, audit = self._engine(path)

            completed = self._save_terminal(
                missions, goal='successful mission', status=MissionStatus.COMPLETED,
                verified=True, retry=1, recovery=1,
            )
            failed = self._save_terminal(
                missions, goal='failed mission', status=MissionStatus.FAILED,
                verified=False,
            )
            replanned = self._save_terminal(
                missions, goal='replanned mission', status=MissionStatus.COMPLETED,
                verified=True, recovery=1,
            )
            missions.add_event(replanned.id, 'mission.replanned', {'new_steps': ['safe recovery']})

            audit.record(
                mission_id=completed.id, session_id='S-TEST', request_summary='search public web',
                tool_name='browser_search', risk_level='MEDIUM', capabilities=['BROWSER_CONTROL'], args={'query': 'x'},
                approval_status='AUTO_ALLOWED', execution_status='SUCCESS', latency_ms=100,
                verification_result='VERIFIED: browser opened',
            )
            audit.record(
                mission_id=failed.id, session_id='S-TEST', request_summary='search public web',
                tool_name='browser_search', risk_level='MEDIUM', capabilities=['BROWSER_CONTROL'], args={'query': 'y'},
                approval_status='AUTO_ALLOWED', execution_status='FAILED', error_type='TOOL_ERROR', latency_ms=300,
                verification_result='FAILED: browser did not open',
            )
            audit.record(
                mission_id=None, session_id='S-TEST', request_summary='sensitive action',
                tool_name='type_text', risk_level='HIGH', capabilities=['KEYBOARD_CONTROL'], args={'text': 'hello'},
                approval_status='DENY', execution_status='DENIED', latency_ms=20,
            )
            audit.record(
                mission_id=None, session_id='S-TEST', request_summary='store secret',
                tool_name='remember_fact', risk_level='MEDIUM', capabilities=['MEMORY_WRITE'], args={'fact': '[redacted test]'},
                approval_status='BLOCKED_SECRET', execution_status='DENIED', latency_ms=5,
            )

            snapshot = engine.evaluate(mission_limit=20, audit_limit=100, persist=True)
            metrics = snapshot.metrics

            self.assertAlmostEqual(metrics['mission_success_rate'].value, 2 / 3)
            self.assertAlmostEqual(metrics['verification_success_rate'].value, 2 / 3)
            self.assertEqual(metrics['replanning_success_rate'].value, 1.0)
            self.assertEqual(metrics['recovery_success_rate'].value, 1.0)
            self.assertAlmostEqual(metrics['tool_success_rate'].value, 0.5)
            self.assertAlmostEqual(metrics['tool_error_rate'].value, 0.5)
            self.assertAlmostEqual(metrics['browser_success_rate'].value, 0.5)
            self.assertEqual(metrics['tool_verification_success_rate'].value, 0.5)
            self.assertEqual(metrics['average_tool_latency_ms'].value, 106.25)
            self.assertEqual(metrics['safety_blocks'].value, 1.0)

    def test_unsupported_accuracy_metrics_are_na_not_fake_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, _ = self._engine(Path(tmp) / 'jarvis.db')
            snapshot = engine.evaluate(persist=False)
            for name in (
                'memory_retrieval_accuracy', 'ui_targeting_accuracy', 'fallback_rate',
                'permission_accuracy', 'safety_violation_rate', 'test_pass_rate',
            ):
                self.assertIsNone(snapshot.metrics[name].value, name)

    def test_history_persists_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _, _ = self._engine(Path(tmp) / 'jarvis.db')
            first = engine.evaluate(persist=True)
            history = engine.history(5)
            self.assertEqual(history[0]['id'], first.id)
            self.assertIn('metrics', history[0])
            self.assertIn('capability_status', history[0])

    def test_public_core_exposes_evaluation_api(self):
        from jarvis.core import JarvisOmega
        self.assertTrue(callable(getattr(JarvisOmega, 'evaluate_self', None)))
        self.assertTrue(callable(getattr(JarvisOmega, 'evaluation_history', None)))


if __name__ == '__main__':
    unittest.main()
