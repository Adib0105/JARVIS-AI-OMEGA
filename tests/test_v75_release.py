import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.evaluation.benchmark import ScenarioResult
from jarvis.self_development.benchmark import SelfImprovementBenchmark
from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.self_development.proposal import ProposalStatus
from jarvis.self_development.release import ControlledReleaseEngine


def git(args, cwd): return subprocess.run(['git', *args], cwd=str(cwd), text=True, capture_output=True, check=True)

@unittest.skipUnless(shutil.which('git'), 'Git required for release tests')
class V75ReleaseTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / 'repo'; repo.mkdir(); git(['init'], repo); git(['config','user.email','jarvis-release@example.com'],repo); git(['config','user.name','JARVIS Release Test'],repo)
        (repo/'hello.py').write_text("def greet():\n    return 'old'\n",encoding='utf-8'); (repo/'tests').mkdir(); (repo/'tests'/'test_hello.py').write_text("import unittest\nfrom hello import greet\nclass T(unittest.TestCase):\n    def test_greet(self): self.assertEqual(greet(), 'old')\n",encoding='utf-8'); git(['add','.'],repo); git(['commit','-m','baseline'],repo); return repo

    def _approved(self, root: Path):
        repo=self._repo(root); dev=SelfDevelopmentEngine(root/'state.db',repo_root=repo,workspace_root=root/'workspace')
        proposal=dev.proposal_from_gap({'capability':'Coding','title':'Update greeting','description':'new behavior','recommended_action':'change implementation plus regression test','evidence':['expected=new']})
        binding=SelfImprovementBenchmark(dev,dev.benchmark); binding.record_baseline(proposal.id,[ScenarioResult('release-greeting','task',False,20)])
        dev.prepare_sandbox(proposal.id); dev.apply_changes(proposal.id,{'hello.py':"def greet():\n    return 'new'\n",'tests/test_hello.py':"import unittest\nfrom hello import greet\nclass T(unittest.TestCase):\n    def test_greet(self): self.assertEqual(greet(), 'new')\n"})
        self.assertEqual(dev.run_tests(proposal.id).status,ProposalStatus.TESTED); binding.record_after(proposal.id,[ScenarioResult('release-greeting','task',True,10)])
        self.assertEqual(dev.review(proposal.id).status,ProposalStatus.AWAITING_APPROVAL); self.assertEqual(dev.approve(proposal.id,explicit_user_approval=True).status,ProposalStatus.APPROVED); return repo,dev,proposal.id

    def test_default_disabled_production_setting_blocks_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo,dev,proposal_id=self._approved(Path(tmp)); release=ControlledReleaseEngine(dev); fake=SimpleNamespace(production_self_modification=False,auto_rollback_enabled=False)
            with patch('jarvis.self_development.release.settings',fake):
                with self.assertRaisesRegex(PermissionError,'disabled by configuration'): release.deploy(proposal_id,explicit_user_approval=True)
            self.assertIn("'old'",(repo/'hello.py').read_text(encoding='utf-8')); dev.sandbox.destroy(proposal_id,delete_branch=True)

    def test_approved_release_then_rollback_preserves_git_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo,dev,proposal_id=self._approved(Path(tmp)); release=ControlledReleaseEngine(dev); fake=SimpleNamespace(production_self_modification=True,auto_rollback_enabled=False)
            with patch('jarvis.self_development.release.settings',fake):
                with self.assertRaises(PermissionError): release.deploy(proposal_id,explicit_user_approval=False)
                deployed=release.deploy(proposal_id,explicit_user_approval=True); self.assertTrue(deployed['ok']); self.assertIn("'new'",(repo/'hello.py').read_text(encoding='utf-8')); self.assertEqual(dev.store.get(proposal_id).status,ProposalStatus.DEPLOYED)
                rolled=release.rollback(proposal_id,explicit_confirmation=True); self.assertTrue(rolled['ok']); self.assertIn("'old'",(repo/'hello.py').read_text(encoding='utf-8')); self.assertEqual(dev.store.get(proposal_id).status,ProposalStatus.ROLLED_BACK); self.assertIn('revert',git(['log','--oneline','-3'],repo).stdout.lower())
            dev.sandbox.destroy(proposal_id,delete_branch=True)

if __name__=='__main__': unittest.main()
