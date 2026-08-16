import tempfile
import unittest
from pathlib import Path

from jarvis.agent.mission import Mission, MissionStatus, VerificationResult
from jarvis.agent.mission_store import MissionStore
from jarvis.evaluation.engine import EvaluationMetric, EvaluationSnapshot, SelfEvaluationEngine
from jarvis.evaluation.gaps import CapabilityGapDetector
from jarvis.security.audit import AuditStore


class FakeRegistry:
    def snapshot(self, *args, **kwargs):
        return [
            {
                'name': 'PDF Tables',
                'status': 'MISSING',
                'detail': 'no table extractor configured',
                'implementation_path': 'jarvis/documents.py',
            },
            {
                'name': 'Memory',
                'status': 'AVAILABLE',
                'detail': '',
                'implementation_path': 'jarvis/memory_v7.py',
            },
        ]


class StaticEvaluation:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def evaluate(self, **kwargs):
        return self.snapshot


class V75GapDetectorTests(unittest.TestCase):
    def _snapshot(self):
        metrics = {
            'mission_success_rate': EvaluationMetric('mission_success_rate', 0.50, 1, 2),
            'tool_success_rate': EvaluationMetric('tool_success_rate', 1.0, 2, 2),
            'verification_success_rate': EvaluationMetric('verification_success_rate', None),
            'recovery_success_rate': EvaluationMetric('recovery_success_rate', None),
            'replanning_success_rate': EvaluationMetric('replanning_success_rate', None),
            'browser_success_rate': EvaluationMetric('browser_success_rate', None),
            'computer_use_success_rate': EvaluationMetric('computer_use_success_rate', None),
            'tool_verification_success_rate': EvaluationMetric('tool_verification_success_rate', None),
        }
        return EvaluationSnapshot(
            id='EVAL-TEST', created_at='2026-01-01T00:00:00+00:00',
            mission_window=2, audit_window=2, metrics=metrics,
            recommendations=(), capability_status=(),
        )

    def _detector(self, path: Path):
        missions = MissionStore(path)
        audit = AuditStore(path)
        registry = FakeRegistry()
        detector = CapabilityGapDetector(
            path,
            evaluation=StaticEvaluation(self._snapshot()),
            missions=missions,
            audit=audit,
            registry=registry,
        )
        return detector, missions, audit

    def test_detects_registry_and_metric_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            detector, _, _ = self._detector(Path(tmp) / 'jarvis.db')
            gaps = detector.detect(persist=False, evaluation_snapshot=self._snapshot())
            titles = {gap.title for gap in gaps}
            self.assertIn('PDF Tables is MISSING', titles)
            self.assertIn('Mission Reliability score below target', titles)

    def test_detects_repeated_tool_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            detector, _, audit = self._detector(Path(tmp) / 'jarvis.db')
            for index in range(3):
                audit.record(
                    mission_id=None, session_id='S', request_summary='same failure',
                    tool_name='read_document', risk_level='MEDIUM', capabilities=['DOCUMENT_READ'],
                    args={'file_path': f'x{index}.pdf'}, approval_status='AUTO_ALLOWED',
                    execution_status='FAILED', error_type='TOOL_ERROR', latency_ms=10,
                )
            gaps = detector.detect(persist=False, evaluation_snapshot=self._snapshot(), audit_limit=50)
            repeated = [gap for gap in gaps if gap.title == 'Repeated read_document failures']
            self.assertEqual(len(repeated), 1)
            self.assertIn('failure_count=3', repeated[0].evidence)

    def test_detects_repeated_mission_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            detector, missions, _ = self._detector(Path(tmp) / 'jarvis.db')
            for goal in ('task one', 'task two'):
                mission = Mission(goal=goal, session_id='S')
                mission.status = MissionStatus.FAILED
                mission.last_error = 'Unable to extract tables from PDFs.'
                mission.final_verification = VerificationResult(False, 'FAILED', 'blocked')
                missions.save(mission)
            gaps = detector.detect(persist=False, evaluation_snapshot=self._snapshot(), mission_limit=20)
            repeated = [gap for gap in gaps if gap.title == 'Repeated mission failure pattern']
            self.assertEqual(len(repeated), 1)
            self.assertIn('count=2', repeated[0].evidence)

    def test_persistence_deduplicates_same_gap_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            detector, _, _ = self._detector(Path(tmp) / 'jarvis.db')
            detector.detect(persist=True, evaluation_snapshot=self._snapshot())
            detector.detect(persist=True, evaluation_snapshot=self._snapshot())
            open_gaps = detector.list_open(100)
            keys = [(item['capability'], item['title'], item['source']) for item in open_gaps]
            self.assertEqual(len(keys), len(set(keys)))

    def test_public_core_exposes_gap_api(self):
        from jarvis.core import JarvisOmega
        self.assertTrue(callable(getattr(JarvisOmega, 'detect_capability_gaps', None)))
        self.assertTrue(callable(getattr(JarvisOmega, 'capability_gap_history', None)))


if __name__ == '__main__':
    unittest.main()
