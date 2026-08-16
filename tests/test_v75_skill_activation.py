import json
import tempfile
import unittest
from pathlib import Path

from jarvis.self_development.proposal import ProposalStatus, ProposalStore
from jarvis.skills.activation import SkillActivationEngine
from jarvis.skills.manager import SkillProposalStatus, SkillRegistry


class V75SkillActivationTests(unittest.TestCase):
    def _setup(self, root: Path, *, deployed: bool):
        db = root / 'state.db'
        registry = SkillRegistry(db)
        proposals = ProposalStore(db)
        skill = registry.propose_from_gap({
            'id': 'GAP-1',
            'capability': 'Browser helper',
            'title': 'Browser helper',
            'description': 'Reusable browser helper.',
            'recommended_action': 'Build a verified helper.',
            'evidence': ['repeated workflow'],
            'severity': 'MEDIUM',
        })
        improvement = proposals.create(
            title='Build skill', capability='Skill:browser_helper', problem='gap',
            objective='ship tested skill', evidence=['gap'], risk='MEDIUM',
        )
        improvement.status = ProposalStatus.DEPLOYED if deployed else ProposalStatus.AWAITING_APPROVAL
        proposals.save(improvement)
        skill = registry.link_improvement(skill.id, improvement.id)

        manifest = skill.manifest
        required = [
            f'skills/{manifest.slug}/skill.json', manifest.implementation,
            *manifest.tests, manifest.documentation,
        ]
        for relative in required:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n' if path.suffix == '.json' else '# verified\n', encoding='utf-8')
        evaluation = root / manifest.evaluation
        evaluation.parent.mkdir(parents=True, exist_ok=True)
        evaluation.write_text(json.dumps({'status': 'PASS', 'score': 1.0}), encoding='utf-8')
        return registry, proposals, skill

    def test_activation_requires_deployed_improvement_and_explicit_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, proposals, skill = self._setup(root, deployed=True)
            engine = SkillActivationEngine(registry, proposals, repo_root=root)
            with self.assertRaises(PermissionError):
                engine.activate(skill.id, explicit_user_approval=False)
            result = engine.activate(skill.id, explicit_user_approval=True)
            self.assertTrue(result['ok'])
            self.assertEqual(result['status'], SkillProposalStatus.ACTIVE.value)

    def test_unreleased_skill_cannot_be_activated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, proposals, skill = self._setup(root, deployed=False)
            engine = SkillActivationEngine(registry, proposals, repo_root=root)
            with self.assertRaises(RuntimeError):
                engine.activate(skill.id, explicit_user_approval=True)


if __name__ == '__main__':
    unittest.main()
