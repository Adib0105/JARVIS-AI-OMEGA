import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.evaluation.benchmark import ScenarioResult
from jarvis.self_development.benchmark import SelfImprovementBenchmark
from jarvis.self_development.builder import SelfDevelopmentBuilder
from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.self_development.policies import SelfDevelopmentPolicy
from jarvis.self_development.proposal import ProposalStatus, ProposalStore


def git(args, cwd):
    return subprocess.run(['git', *args], cwd=str(cwd), text=True, capture_output=True, check=True)


@unittest.skipUnless(shutil.which('git'), 'Git is required for self-development worktree tests')
class V75SelfDevelopmentTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / 'repo'; repo.mkdir(); git(['init'], repo)
        git(['config', 'user.email', 'jarvis-test@example.com'], repo); git(['config', 'user.name', 'JARVIS Test'], repo)
        (repo / 'hello.py').write_text("def greet():\n    return 'old'\n", encoding='utf-8'); (repo / 'tests').mkdir()
        (repo / 'tests' / 'test_hello.py').write_text("import unittest\nfrom hello import greet\n\nclass T(unittest.TestCase):\n    def test_greet(self):\n        self.assertEqual(greet(), 'old')\n", encoding='utf-8')
        git(['add', '.'], repo); git(['commit', '-m', 'baseline'], repo); return repo

    def _tested(self, root: Path):
        repo = self._repo(root); engine = SelfDevelopmentEngine(root / 'state.db', repo_root=repo, workspace_root=root / 'workspace')
        proposal = engine.proposal_from_gap({'id':'GAP-TEST','capability':'Coding','title':'Fix greeting behavior','description':'Regression scenario','recommended_action':'Change greeting with a regression test.','evidence':['expected=new'],'severity':'MEDIUM'})
        engine.prepare_sandbox(proposal.id)
        engine.apply_changes(proposal.id, {'hello.py':"def greet():\n    return 'new'\n", 'tests/test_hello.py':"import unittest\nfrom hello import greet\n\nclass T(unittest.TestCase):\n    def test_greet(self):\n        self.assertEqual(greet(), 'new')\n"})
        self.assertEqual(engine.run_tests(proposal.id).status, ProposalStatus.TESTED)
        return repo, engine, proposal

    @staticmethod
    def _results(success: bool, latency: float = 10.0):
        return [ScenarioResult('greeting-behavior', 'task', success, latency)]

    def test_policy_blocks_security_core_and_secret_paths(self):
        policy = SelfDevelopmentPolicy()
        for path in ('jarvis/security/policy.py', 'jarvis/self_development/rollback.py', '.env'):
            allowed, _ = policy.path_allowed(path); self.assertFalse(allowed, path)
        self.assertTrue(policy.path_allowed('jarvis/documents.py')[0])

    def test_policy_blocks_self_development_control_plane(self):
        policy = SelfDevelopmentPolicy()
        protected = (
            'jarvis/self_development/policies.py',
            'jarvis/self_development/sandbox.py',
            'jarvis/self_development/builder.py',
            'jarvis/self_development/git_manager.py',
            'jarvis/self_development/lease.py',
            'jarvis/self_development/rollback.py',
            'jarvis/self_development/release.py',
            'jarvis/self_development/engine.py',
            'jarvis/self_development/tester.py',
            'jarvis/skills/activation.py',
        )
        for path in protected:
            allowed, reason = policy.path_allowed(path)
            self.assertFalse(allowed, path)
            self.assertIn('control-plane', reason)

    def test_policy_normalization_cannot_alias_protected_control_file(self):
        policy = SelfDevelopmentPolicy()
        for path in (
            './jarvis/self_development/release.py',
            'jarvis\\self_development\\sandbox.py',
            'jarvis/self_development/../self_development/release.py',
        ):
            allowed, _ = policy.path_allowed(path)
            self.assertFalse(allowed, path)

    def test_builder_cannot_escape_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = SelfDevelopmentBuilder(Path(tmp))
            with self.assertRaises(PermissionError): builder.write_text('../escape.py', 'x = 1')
            with self.assertRaises(PermissionError): builder.write_text('jarvis/security/policy.py', 'unsafe = True')
            with self.assertRaises(PermissionError): builder.write_text('jarvis/self_development/release.py', 'unsafe = True')
            with self.assertRaises(PermissionError): builder.write_text('jarvis/self_development/sandbox.py', 'unsafe = True')

    def test_builder_cannot_alias_protected_file_through_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected = root / 'jarvis' / 'security' / 'policy.py'
            protected.parent.mkdir(parents=True)
            protected.write_text('SAFE = True\n', encoding='utf-8')
            alias = root / 'harmless.py'
            try:
                alias.symlink_to(protected)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'symlink creation unavailable on this platform: {exc}')

            builder = SelfDevelopmentBuilder(root)
            with self.assertRaises(PermissionError):
                builder.write_text('harmless.py', 'SAFE = False\n')
            self.assertEqual(protected.read_text(encoding='utf-8'), 'SAFE = True\n')

    def test_proposal_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProposalStore(Path(tmp) / 'state.db')
            from jarvis.self_development.proposal import ImprovementProposal
            proposal = ImprovementProposal(title='Improve docs', capability='Documents', problem='gap', objective='fix', evidence=['e1'])
            store.save(proposal); loaded = store.get(proposal.id)
            self.assertIsNotNone(loaded); self.assertEqual(loaded.title, proposal.title); self.assertEqual(loaded.status, ProposalStatus.PROPOSED)

    def test_end_to_end_pipeline_never_changes_production_before_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo, engine, proposal = self._tested(root)
            binding = SelfImprovementBenchmark(engine, engine.benchmark)
            binding.record_baseline(proposal.id, self._results(False, 20)); binding.record_after(proposal.id, self._results(True, 10))
            reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.AWAITING_APPROVAL); self.assertTrue(reviewed.evaluation_summary['passed']); self.assertEqual(reviewed.evaluation_summary['evidence_status'], 'VALID')
            self.assertTrue(reviewed.evaluation_summary['benchmark_before_id'].startswith('BENCH-')); self.assertTrue(reviewed.evaluation_summary['benchmark_after_id'].startswith('BENCH-'))
            with self.assertRaises(PermissionError): engine.approve(proposal.id, explicit_user_approval=False)
            self.assertEqual(engine.approve(proposal.id, explicit_user_approval=True).status, ProposalStatus.APPROVED)
            self.assertEqual((repo / 'hello.py').read_text(encoding='utf-8'), "def greet():\n    return 'old'\n"); engine.sandbox.destroy(proposal.id, delete_branch=True)

    def test_review_missing_before_is_insufficient_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, engine, proposal = self._tested(Path(tmp)); reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.FAILED); self.assertEqual(reviewed.evaluation_summary['evidence_status'], 'INSUFFICIENT EVIDENCE'); self.assertIn('Missing persisted baseline benchmark evidence.', reviewed.evaluation_summary['evidence_reasons'])

    def test_review_missing_after_is_insufficient_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, engine, proposal = self._tested(Path(tmp)); SelfImprovementBenchmark(engine, engine.benchmark).record_baseline(proposal.id, self._results(False)); reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.FAILED); self.assertIn('Missing persisted candidate benchmark evidence.', reviewed.evaluation_summary['evidence_reasons'])

    def test_review_invalid_benchmark_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, engine, proposal = self._tested(root); binding = SelfImprovementBenchmark(engine, engine.benchmark); binding.record_baseline(proposal.id, self._results(False)); binding.record_after(proposal.id, self._results(True))
            other = engine.benchmark.record('OTHER:after', self._results(True)); stored = engine.store.get(proposal.id); stored.evaluation_summary['benchmark_after_id'] = other.id; engine.store.save(stored)
            reviewed = engine.review(proposal.id); self.assertEqual(reviewed.status, ProposalStatus.FAILED); self.assertIn('Candidate benchmark is not bound to this proposal.', reviewed.evaluation_summary['evidence_reasons'])

    def test_review_genuine_regression_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, engine, proposal = self._tested(Path(tmp)); binding = SelfImprovementBenchmark(engine, engine.benchmark); binding.record_baseline(proposal.id, self._results(True, 10)); binding.record_after(proposal.id, self._results(False, 20)); reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.FAILED); self.assertFalse(reviewed.evaluation_summary['passed']); self.assertTrue(reviewed.evaluation_summary['regressed_metrics'])

    def test_review_genuine_improvement_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, engine, proposal = self._tested(Path(tmp)); binding = SelfImprovementBenchmark(engine, engine.benchmark); before = binding.record_baseline(proposal.id, self._results(False, 20)); result = binding.record_after(proposal.id, self._results(True, 10)); reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.AWAITING_APPROVAL); self.assertTrue(reviewed.evaluation_summary['passed']); self.assertEqual(reviewed.evaluation_summary['benchmark_before_id'], before['id']); self.assertEqual(reviewed.evaluation_summary['benchmark_after_id'], result.after_id)


if __name__ == '__main__': unittest.main()
