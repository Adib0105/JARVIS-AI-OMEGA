import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.self_development.builder import SelfDevelopmentBuilder
from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.self_development.policies import SelfDevelopmentPolicy
from jarvis.self_development.proposal import ProposalStatus, ProposalStore


def git(args, cwd):
    return subprocess.run(['git', *args], cwd=str(cwd), text=True, capture_output=True, check=True)


@unittest.skipUnless(shutil.which('git'), 'Git is required for self-development worktree tests')
class V75SelfDevelopmentTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / 'repo'
        repo.mkdir()
        git(['init'], repo)
        git(['config', 'user.email', 'jarvis-test@example.com'], repo)
        git(['config', 'user.name', 'JARVIS Test'], repo)
        (repo / 'hello.py').write_text("def greet():\n    return 'old'\n", encoding='utf-8')
        (repo / 'tests').mkdir()
        (repo / 'tests' / 'test_hello.py').write_text(
            "import unittest\nfrom hello import greet\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_greet(self):\n"
            "        self.assertEqual(greet(), 'old')\n",
            encoding='utf-8',
        )
        git(['add', '.'], repo)
        git(['commit', '-m', 'baseline'], repo)
        return repo

    def test_policy_blocks_security_core_and_secret_paths(self):
        policy = SelfDevelopmentPolicy()
        for path in (
            'jarvis/security/policy.py',
            'jarvis/self_development/release.py',
            '.github/workflows/ci.yml',
            'tests/evaluation/test_security_adversarial.py',
            '.env',
        ):
            allowed, _ = policy.path_allowed(path)
            self.assertFalse(allowed, path)
        allowed, _ = policy.path_allowed('jarvis/documents.py')
        self.assertTrue(allowed)

    def test_builder_cannot_escape_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = SelfDevelopmentBuilder(root)
            with self.assertRaises(PermissionError):
                builder.write_text('../escape.py', 'x = 1')
            with self.assertRaises(PermissionError):
                builder.write_text('jarvis/security/policy.py', 'unsafe = True')

    def test_proposal_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProposalStore(Path(tmp) / 'state.db')
            from jarvis.self_development.proposal import ImprovementProposal
            proposal = ImprovementProposal(
                title='Improve docs', capability='Documents', problem='gap', objective='fix', evidence=['e1']
            )
            store.save(proposal)
            loaded = store.get(proposal.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.title, proposal.title)
            self.assertEqual(loaded.status, ProposalStatus.PROPOSED)

    def test_end_to_end_pipeline_never_changes_production_before_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            engine = SelfDevelopmentEngine(
                root / 'state.db', repo_root=repo, workspace_root=root / 'workspace'
            )
            proposal = engine.proposal_from_gap({
                'id': 'GAP-TEST',
                'capability': 'Coding',
                'title': 'Fix greeting behavior',
                'description': 'Regression scenario',
                'recommended_action': 'Change greeting with a regression test.',
                'evidence': ['expected=new'],
                'severity': 'MEDIUM',
            })
            prepared = engine.prepare_sandbox(proposal.id)
            self.assertEqual(prepared.status, ProposalStatus.SANDBOX_READY)
            self.assertTrue(Path(prepared.sandbox_path).exists())
            self.assertEqual((repo / 'hello.py').read_text(encoding='utf-8'), "def greet():\n    return 'old'\n")

            changed = engine.apply_changes(proposal.id, {
                'hello.py': "def greet():\n    return 'new'\n",
                'tests/test_hello.py': (
                    "import unittest\nfrom hello import greet\n\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_greet(self):\n"
                    "        self.assertEqual(greet(), 'new')\n"
                ),
            })
            self.assertIn('hello.py', changed.changed_files)
            tested = engine.run_tests(proposal.id)
            self.assertEqual(tested.status, ProposalStatus.TESTED)
            reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.AWAITING_APPROVAL)
            self.assertTrue(reviewed.evaluation_summary['passed'])
            self.assertIn('hello.py', reviewed.changed_files)
            self.assertIn('tests/test_hello.py', reviewed.changed_files)

            with self.assertRaises(PermissionError):
                engine.approve(proposal.id, explicit_user_approval=False)
            approved = engine.approve(proposal.id, explicit_user_approval=True)
            self.assertEqual(approved.status, ProposalStatus.APPROVED)

            # Approval is only a state transition. No production merge/deploy exists here.
            self.assertEqual((repo / 'hello.py').read_text(encoding='utf-8'), "def greet():\n    return 'old'\n")
            engine.sandbox.destroy(proposal.id, delete_branch=True)

    def test_untracked_file_content_and_lines_are_included_in_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._repo(root)
            engine = SelfDevelopmentEngine(
                root / 'state.db', repo_root=repo, workspace_root=root / 'workspace'
            )
            proposal = engine.proposal_from_gap({
                'capability': 'Docs',
                'title': 'Add generated notes',
                'description': 'exercise untracked review evidence',
                'recommended_action': 'add a bounded document',
                'evidence': ['review-required'],
            })
            prepared = engine.prepare_sandbox(proposal.id)
            worktree = Path(prepared.sandbox_path)
            generated = worktree / 'docs' / 'generated.md'
            generated.parent.mkdir()
            generated.write_text('\n'.join(f'line {index}' for index in range(1301)), encoding='utf-8')

            files, lines = engine.sandbox.git.diff_stats(worktree)
            diff = engine.sandbox.git.diff(worktree)
            self.assertIn('docs/generated.md', files)
            self.assertGreater(lines, engine.policy.max_lines_changed)
            self.assertIn('line 1300', diff)

            self.assertEqual(engine.run_tests(proposal.id).status, ProposalStatus.TESTED)
            reviewed = engine.review(proposal.id)
            self.assertEqual(reviewed.status, ProposalStatus.FAILED)
            self.assertTrue(any('line limit exceeded' in reason for reason in reviewed.policy_summary['review_reasons']))
            engine.sandbox.destroy(proposal.id, delete_branch=True)


if __name__ == '__main__':
    unittest.main()
