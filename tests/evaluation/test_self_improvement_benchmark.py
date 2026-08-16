import tempfile
import unittest
from pathlib import Path

from jarvis.evaluation.benchmark import AgentEvaluationBenchmark, ScenarioResult
from jarvis.self_development.benchmark import SelfImprovementBenchmark
from jarvis.self_development.engine import SelfDevelopmentEngine


class V75SelfImprovementBenchmarkTests(unittest.TestCase):
    def test_before_after_metrics_are_bound_to_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # This test only exercises proposal/evaluation persistence; no Git sandbox is created.
            development = SelfDevelopmentEngine.__new__(SelfDevelopmentEngine)
            from jarvis.self_development.proposal import ProposalStore
            development.store = ProposalStore(root / 'state.db')
            proposal = development.store.create(
                title='Improve browser targeting', capability='Browser', problem='low score',
                objective='raise deterministic browser scenario success', evidence=['baseline failure'], risk='MEDIUM',
            )
            benchmark = AgentEvaluationBenchmark(root / 'state.db')
            binding = SelfImprovementBenchmark(development, benchmark)
            before = binding.record_baseline(proposal.id, [ScenarioResult('b1', 'browser', False, 20)])
            result = binding.record_after(proposal.id, [ScenarioResult('b1', 'browser', True, 15)])
            self.assertEqual(result.before_id, before['id'])
            self.assertTrue(result.comparison['successful_improvement'])
            stored = development.store.get(proposal.id)
            self.assertEqual(stored.evaluation_summary['benchmark_after_id'], result.after_id)


if __name__ == '__main__':
    unittest.main()
