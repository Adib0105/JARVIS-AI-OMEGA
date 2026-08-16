import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.self_development.engine import SelfDevelopmentEngine
from jarvis.skills.builder import SkillBuildEngine
from jarvis.skills.manager import SkillProposalStatus, SkillRegistry


def git(args, cwd):
    return subprocess.run(['git', *args], cwd=str(cwd), text=True, capture_output=True, check=True)


@unittest.skipUnless(shutil.which('git'), 'Git required for skill builder tests')
class V75SkillBuilderTests(unittest.TestCase):
    def _repo(self, root: Path) -> Path:
        repo = root / 'repo'; repo.mkdir()
        git(['init'], repo)
        git(['config', 'user.email', 'skill-test@example.com'], repo)
        git(['config', 'user.name', 'Skill Test'], repo)
        (repo / 'base.py').write_text('VALUE = 1\n', encoding='utf-8')
        (repo / 'tests').mkdir()
        (repo / 'tests' / 'test_base.py').write_text(
            'import unittest\nfrom base import VALUE\nclass T(unittest.TestCase):\n    def test_value(self): self.assertEqual(VALUE, 1)\n',
            encoding='utf-8',
        )
        git(['add', '.'], repo); git(['commit', '-m', 'baseline'], repo)
        return repo

    def test_prepare_creates_required_inactive_skill_scaffold_in_sandbox_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = self._repo(root)
            registry = SkillRegistry(root / 'state.db')
            skill = registry.propose_from_gap({
                'capability': 'Excel Automation', 'title': 'Excel Automation',
                'description': 'Reusable Excel analysis.', 'recommended_action': 'Build skill.',
                'evidence': ['repeated workflow'], 'severity': 'MEDIUM', 'permissions': ['FILE_READ'],
            })
            development = SelfDevelopmentEngine(root / 'state.db', repo_root=repo, workspace_root=root / 'workspace')
            builder = SkillBuildEngine(registry, development, lambda *_: '{}')
            result = builder.prepare(skill.id)
            prepared = registry.get(skill.id)
            self.assertEqual(prepared.status, SkillProposalStatus.BUILDING)
            sandbox = Path(result['improvement']['sandbox_path'])
            self.assertTrue((sandbox / 'skills' / 'excel_automation' / 'skill.json').exists())
            self.assertTrue((sandbox / 'skills' / 'excel_automation' / 'implementation.py').exists())
            self.assertTrue((sandbox / 'skills' / 'excel_automation' / 'tests' / 'test_skill.py').exists())
            self.assertTrue((sandbox / 'skills' / 'excel_automation' / 'README.md').exists())
            self.assertTrue((sandbox / 'skills' / 'excel_automation' / 'evaluation.json').exists())
            self.assertFalse((repo / 'skills').exists())
            development.sandbox.destroy(prepared.improvement_proposal_id, delete_branch=True)


if __name__ == '__main__':
    unittest.main()
