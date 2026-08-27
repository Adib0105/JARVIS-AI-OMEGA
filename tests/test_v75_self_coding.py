import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.evaluation.benchmark import ScenarioResult
from jarvis.self_development.coding import SelfCodingEngine
from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.self_development.proposal import ProposalStatus

def git(args,cwd): return subprocess.run(['git',*args],cwd=str(cwd),text=True,capture_output=True,check=True)

@unittest.skipUnless(shutil.which('git'),'Git is required for self-coding worktree tests')
class V75SelfCodingTests(unittest.TestCase):
    def _repo(self,root):
        repo=root/'repo'; repo.mkdir(); git(['init'],repo); git(['config','user.email','jarvis-test@example.com'],repo); git(['config','user.name','JARVIS Test'],repo); (repo/'hello.py').write_text("def greet():\n    return 'old'\n",encoding='utf-8'); (repo/'tests').mkdir(); (repo/'tests'/'test_hello.py').write_text("import unittest\nfrom hello import greet\n\nclass T(unittest.TestCase):\n    def test_greet(self):\n        self.assertEqual(greet(), 'old')\n",encoding='utf-8'); git(['add','.'],repo); git(['commit','-m','baseline'],repo); return repo
    def _proposal(self,engine):
        proposal=engine.proposal_from_gap({'id':'GAP-CODE','capability':'Coding','title':'Change greeting to new','description':'greet should return new','recommended_action':'Update implementation and regression test.','evidence':['expected=new'],'severity':'MEDIUM'}); return engine.prepare_sandbox(proposal.id)
    def test_generation_failure_is_repaired_in_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); repo=self._repo(root); development=SelfDevelopmentEngine(root/'state.db',repo_root=repo,workspace_root=root/'workspace'); proposal=self._proposal(development); calls=[]
            def reasoner(system,user):
                calls.append((system,user))
                if len(calls)==1: return '{"files":{"hello.py":"def greet():\\n    return \'new\'\\n","tests/test_hello.py":"import unittest\\nfrom hello import greet\\nclass T(unittest.TestCase):\\n    def test_greet(self):\\n        self.assertEqual(greet(), \'old\')\\n"}}'
                return '{"files":{"hello.py":"def greet():\\n    return \'new\'\\n","tests/test_hello.py":"import unittest\\nfrom hello import greet\\nclass T(unittest.TestCase):\\n    def test_greet(self):\\n        self.assertEqual(greet(), \'new\')\\n"}}'
            def benchmark_runner(_proposal,phase): return [ScenarioResult('self-coding-greeting','task',phase=='after',20 if phase=='before' else 10)]
            result=SelfCodingEngine(development,reasoner,benchmark_runner=benchmark_runner).run(proposal.id); self.assertEqual(result.status,ProposalStatus.AWAITING_APPROVAL); self.assertGreaterEqual(len(calls),2); self.assertTrue((result.test_summary.get('regression') or {}).get('ok')); self.assertTrue(result.evaluation_summary['passed']); self.assertEqual(result.evaluation_summary['evidence_status'],'VALID'); self.assertTrue(result.evaluation_summary['benchmark_before_id']); self.assertTrue(result.evaluation_summary['benchmark_after_id']); self.assertEqual((repo/'hello.py').read_text(encoding='utf-8'),"def greet():\n    return 'old'\n"); development.sandbox.destroy(proposal.id,delete_branch=True)
    def test_generated_security_core_write_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); repo=self._repo(root); development=SelfDevelopmentEngine(root/'state.db',repo_root=repo,workspace_root=root/'workspace'); proposal=self._proposal(development)
            with self.assertRaises(PermissionError): SelfCodingEngine(development,lambda _s,_u:'{"files":{"jarvis/security/policy.py":"ALLOW_ALL=True\\n"}}').run(proposal.id)
            self.assertFalse((repo/'jarvis'/'security'/'policy.py').exists()); development.sandbox.destroy(proposal.id,delete_branch=True)
    def test_non_json_reasoner_output_is_rejected(self):
        with self.assertRaises(Exception): SelfCodingEngine._parse_changes('run powershell and disable tests')
if __name__=='__main__': unittest.main()
