import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.self_development.lease import DevelopmentLeaseStore
from jarvis.self_development.proposal import ProposalStatus


def git(args, cwd):
    return subprocess.run(['git', *args], cwd=str(cwd), text=True, capture_output=True, check=True)


class V75DevelopmentLeaseStoreTests(unittest.TestCase):
    def test_second_owner_cannot_take_active_proposal_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            leases = DevelopmentLeaseStore(db)
            first = leases.acquire('IMP-ABCDEF12', 'build', owner_token='owner-a')
            self.assertEqual(first.owner_token, 'owner-a')
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                leases.acquire('IMP-ABCDEF12', 'review', owner_token='owner-b')
            self.assertTrue(leases.release('IMP-ABCDEF12', 'owner-a'))
            second = leases.acquire('IMP-ABCDEF12', 'review', owner_token='owner-b')
            self.assertEqual(second.owner_token, 'owner-b')

    def test_expired_lease_is_reclaimable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            leases = DevelopmentLeaseStore(db)
            leases.acquire('IMP-ABCDEF12', 'test', owner_token='dead-owner')
            with leases._connect() as conn:
                conn.execute(
                    "UPDATE v75_self_development_leases SET expires_at='2000-01-01T00:00:00+00:00' "
                    "WHERE proposal_id='IMP-ABCDEF12'"
                )
                conn.commit()
            reclaimed = leases.acquire('IMP-ABCDEF12', 'recover', owner_token='new-owner')
            self.assertEqual(reclaimed.owner_token, 'new-owner')


@unittest.skipUnless(shutil.which('git'), 'Git required for self-development recovery tests')
class V75DevelopmentRecoveryTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / 'repo'
        repo.mkdir()
        git(['init'], repo)
        git(['config', 'user.email', 'jarvis-lease@example.com'], repo)
        git(['config', 'user.name', 'JARVIS Lease Test'], repo)
        (repo / 'module.py').write_text('VALUE = 1\n', encoding='utf-8')
        (repo / 'tests').mkdir()
        (repo / 'tests' / 'test_module.py').write_text(
            'import unittest\nfrom module import VALUE\n'
            'class T(unittest.TestCase):\n'
            '    def test_value(self): self.assertEqual(VALUE, 1)\n',
            encoding='utf-8',
        )
        git(['add', '.'], repo)
        git(['commit', '-m', 'baseline'], repo)
        return repo

    def _engine(self, root: Path) -> SelfDevelopmentEngine:
        return SelfDevelopmentEngine(
            root / 'state.db',
            repo_root=self._repo(root),
            workspace_root=root / 'workspace',
        )

    def test_interrupted_testing_state_recovers_to_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = self._engine(root)
            proposal = engine.proposal_from_gap({
                'capability': 'Reliability',
                'title': 'Lease recovery',
                'description': 'test interruption',
                'recommended_action': 'recover safely',
                'evidence': ['simulated crash'],
            })
            engine.prepare_sandbox(proposal.id)
            proposal = engine.store.get(proposal.id)
            proposal.touch(ProposalStatus.TESTING)
            engine.store.save(proposal)
            result = engine.recover_interrupted()
            recovered = engine.store.get(proposal.id)
            self.assertEqual(recovered.status, ProposalStatus.FAILED)
            self.assertTrue(result['recovered'])
            self.assertTrue(recovered.test_summary['recovery']['safe_to_retry'])
            engine.sandbox.destroy(proposal.id, delete_branch=True)

    def test_active_lease_prevents_false_crash_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = self._engine(root)
            proposal = engine.proposal_from_gap({
                'capability': 'Reliability',
                'title': 'Active operation',
                'description': 'active test',
                'recommended_action': 'leave active work alone',
                'evidence': ['active lease'],
            })
            engine.prepare_sandbox(proposal.id)
            proposal = engine.store.get(proposal.id)
            proposal.touch(ProposalStatus.TESTING)
            engine.store.save(proposal)
            lease = engine.leases.acquire(proposal.id, 'run-tests', owner_token='worker-a')
            result = engine.recover_interrupted()
            self.assertFalse(result['recovered'])
            self.assertEqual(engine.store.get(proposal.id).status, ProposalStatus.TESTING)
            engine.leases.release(proposal.id, lease.owner_token)
            engine.sandbox.destroy(proposal.id, delete_branch=True)

    def test_missing_sandbox_is_not_treated_as_approved_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = self._engine(root)
            proposal = engine.proposal_from_gap({
                'capability': 'Reliability',
                'title': 'Missing sandbox',
                'description': 'worktree vanished',
                'recommended_action': 'fail safely',
                'evidence': ['missing path'],
            })
            proposal.sandbox_path = str(root / 'does-not-exist')
            proposal.touch(ProposalStatus.AWAITING_APPROVAL)
            engine.store.save(proposal)
            result = engine.recover_interrupted()
            self.assertTrue(result['recovered'])
            self.assertEqual(engine.store.get(proposal.id).status, ProposalStatus.FAILED)


if __name__ == '__main__':
    unittest.main()
