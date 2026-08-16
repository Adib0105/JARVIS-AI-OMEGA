from __future__ import annotations

import json
from dataclasses import asdict

from ..self_development.coding import SelfCodingEngine
from ..self_development.engine import SelfDevelopmentEngine
from ..self_development.proposal import ProposalStatus
from .manager import SkillProposal, SkillProposalStatus, SkillRegistry


class SkillBuildEngine:
    """Turn an inactive skill proposal into a reviewed sandbox experiment.

    The engine never activates or deploys the skill. It reuses the immutable-core,
    Git-worktree, full-test and diff-review gates from SelfDevelopmentEngine.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        development: SelfDevelopmentEngine,
        reasoner,
    ) -> None:
        self.registry = registry
        self.development = development
        self.reasoner = reasoner

    @staticmethod
    def _gap(skill: SkillProposal) -> dict:
        manifest = skill.manifest
        return {
            'id': skill.source_gap_id or skill.id,
            'capability': f'Skill:{manifest.slug}',
            'title': f'Build reusable skill: {manifest.name}',
            'description': skill.problem,
            'recommended_action': skill.objective,
            'evidence': list(skill.evidence) + [
                'Required skill manifest: ' + json.dumps(manifest.as_dict(), ensure_ascii=False),
                'Skill must remain inactive until tests, security review, release approval and activation.',
            ],
            'severity': manifest.risk,
        }

    @staticmethod
    def _scaffold(skill: SkillProposal) -> dict[str, str]:
        manifest = skill.manifest
        skill_json = {
            'name': manifest.name,
            'slug': manifest.slug,
            'version': manifest.version,
            'description': manifest.description,
            'permissions': list(manifest.permissions),
            'risk': manifest.risk,
            'implementation': manifest.implementation,
            'tests': list(manifest.tests),
            'documentation': manifest.documentation,
            'evaluation': manifest.evaluation,
            'status': 'EXPERIMENTAL',
        }
        return {
            f'skills/{manifest.slug}/skill.json': json.dumps(skill_json, indent=2, ensure_ascii=False) + '\n',
            manifest.implementation: (
                '"""JARVIS skill implementation placeholder.\n\n'
                'The bounded self-coding worker must replace this with the tested implementation.\n'
                '"""\n\n'
                'def skill_status():\n'
                '    return {"status": "EXPERIMENTAL", "ready": False}\n'
            ),
            manifest.tests[0]: (
                'import unittest\n\n'
                'class SkillContractTests(unittest.TestCase):\n'
                '    def test_placeholder_requires_real_implementation(self):\n'
                '        self.fail("Skill implementation has not been generated yet")\n\n'
                'if __name__ == "__main__":\n'
                '    unittest.main()\n'
            ),
            manifest.documentation: (
                f'# {manifest.name}\n\nStatus: EXPERIMENTAL / NOT ACTIVE\n\n'
                f'{manifest.description}\n\n'
                'This skill may be activated only after sandbox tests, security review, evaluation and controlled release.\n'
            ),
            manifest.evaluation: json.dumps({
                'status': 'NOT_EVALUATED',
                'benchmarks': [],
                'notes': ['Populate with measured before/after results before activation.'],
            }, indent=2) + '\n',
        }

    def prepare(self, skill_id: str) -> dict:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        if skill.status not in {SkillProposalStatus.PROPOSED, SkillProposalStatus.FAILED}:
            raise RuntimeError(f'Skill {skill_id} is {skill.status.value}; expected PROPOSED/FAILED.')
        proposal = self.development.proposal_from_gap(self._gap(skill))
        proposal = self.development.prepare_sandbox(proposal.id)
        self.development.apply_changes(proposal.id, self._scaffold(skill))
        skill.improvement_proposal_id = proposal.id
        skill.status = SkillProposalStatus.BUILDING
        self.registry.save(skill)
        return {'skill': skill.as_dict(), 'improvement': proposal.as_dict()}

    def build(self, skill_id: str) -> dict:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        if skill.status != SkillProposalStatus.BUILDING or not skill.improvement_proposal_id:
            raise RuntimeError('Prepare the skill sandbox before build.')

        improvement = self.development.store.get(skill.improvement_proposal_id)
        if improvement is None:
            raise RuntimeError('Linked improvement proposal is missing.')
        # Add skill-specific constraints to the existing proposal evidence so the
        # self-coder sees the exact manifest and cannot silently change permissions.
        improvement.evidence.append(
            'Skill manifest permissions/risk/version are fixed for this build; do not broaden them.'
        )
        self.development.store.save(improvement)
        result = SelfCodingEngine(self.development, self.reasoner).run(improvement.id)
        if result.status == ProposalStatus.AWAITING_APPROVAL:
            skill.status = SkillProposalStatus.AWAITING_APPROVAL
        elif result.status == ProposalStatus.TESTED:
            skill.status = SkillProposalStatus.TESTED
        else:
            skill.status = SkillProposalStatus.FAILED
        self.registry.save(skill)
        return {'skill': skill.as_dict(), 'improvement': result.as_dict()}

    def reject(self, skill_id: str) -> dict:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        skill.status = SkillProposalStatus.REJECTED
        self.registry.save(skill)
        return skill.as_dict()
