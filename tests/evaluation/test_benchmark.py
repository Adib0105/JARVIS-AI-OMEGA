import tempfile
import unittest
from pathlib import Path

from jarvis.evaluation.benchmark import AgentEvaluationBenchmark, ScenarioResult


class V75BenchmarkTests(unittest.TestCase):
    def test_metrics_are_objective_scenario_aggregates(self):
        results = [
            ScenarioResult('task-1', 'task', True, 10),
            ScenarioResult('task-2', 'task', False, 20),
            ScenarioResult('safe-1', 'safety', True, 5),
            ScenarioResult('browser-1', 'browser', True, 15),
        ]
        metrics = AgentEvaluationBenchmark.metrics_for(results)
        self.assertEqual(metrics['task_success_rate'], 0.5)
        self.assertEqual(metrics['safety_pass_rate'], 1.0)
        self.assertEqual(metrics['browser_accuracy'], 1.0)
        self.assertIsNone(metrics['memory_accuracy'])
        self.assertEqual(metrics['average_latency_ms'], 12.5)

    def test_history_and_before_after_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            bench = AgentEvaluationBenchmark(Path(tmp) / 'jarvis.db')
            before = bench.record('before', [
                ScenarioResult('a', 'task', False, 20),
                ScenarioResult('b', 'safety', True, 10),
            ])
            after = bench.record('after', [
                ScenarioResult('a', 'task', True, 10),
                ScenarioResult('b', 'safety', True, 8),
            ])
            comparison = bench.compare(before.as_dict(), after.as_dict())
            self.assertIn('task_success_rate', comparison['improvements'])
            self.assertIn('average_latency_ms', comparison['improvements'])
            self.assertFalse(comparison['regressions'])
            self.assertTrue(comparison['successful_improvement'])
            self.assertEqual(bench.history(2)[0]['id'], after.id)

    def test_case_runner_captures_failure_without_crashing_suite(self):
        result = AgentEvaluationBenchmark.run_case('boom', 'tool', lambda: (_ for _ in ()).throw(RuntimeError('x')))
        self.assertFalse(result.success)
        self.assertIn('RuntimeError', result.detail)


if __name__ == '__main__':
    unittest.main()
