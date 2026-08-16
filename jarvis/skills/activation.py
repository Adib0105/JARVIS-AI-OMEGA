from __future__ import annotations

import json
from pathlib import Path

from ..config import ROOT
from ..self_development.proposal import ProposalStatus, ProposalStore
from .manager import SkillProposalStatus, SkillRegistry


class SkillActivationEngine:
    """Activate a generated skill only after its reviewed code is deployed.

    Activation is metadata/registry state; it never merges code. The linked
    self-development proposal must already have passed the controlled release engine.
    """

    ACCEPTED_EVALUATION = {'PASS', 'PASSED', 'VERIFIED', 'READY'}

    def __init__(
        self,
        registry: SkillRegistry,
        proposal_store: ProposalStore,
        *,
        repo_root: Path | None = None,
    ) -> None:
        self.registry = registry
        self.proposal_store = proposal_store
        self.repo_root = Path(repo_root or ROOT).resolve()

    def _safe_repo_file(self, relative: str) -> Path:
        target = (self.repo_root / relative).resolve()
        try:
            target.relative_to(self.repo_root)
        except ValueError as exc:
            raise PermissionError(f'Skill path escapes repository root: {relative}') from exc
        return target

    def _verify_files(self, skill) -> dict:
        manifest = skill.manifest
        required = [
            f'skills/{manifest.slug}/skill.json',
            manifest.implementation,
            *manifest.tests,
            manifest.documentation,
            manifest.evaluation,
        ]
        missing = [path for path in required if not self._safe_repo_file(path).is_file()]
        if missing:
            raise RuntimeError('Deployed skill is incomplete; missing: ' + ', '.join(missing))

        evaluation_path = self._safe_repo_file(manifest.evaluation)
        try:
            evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise RuntimeError(f'Skill evaluation metadata is invalid: {type(exc).__name__}: {exc}') from exc
        status = str(evaluation.get('status') or '').strip().upper()
        if status not in self.ACCEPTED_EVALUATION:
            raise RuntimeError(
                f'Skill evaluation status is {status or "MISSING"}; expected one of {sorted(self.ACCEPTED_EVALUATION)}.'
            )
        return {'required_files': required, 'evaluation': evaluation}

    def activate(self, skill_id: str, *, explicit_user_approval: bool) -> dict:
        if not explicit_user_approval:
            raise PermissionError('Explicit skill activation approval is required.')
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        if not skill.improvement_proposal_id:
            raise RuntimeError('Skill is not linked to a controlled self-development proposal.')
        improvement = self.proposal_store.get(skill.improvement_proposal_id)
        if improvement is None:
            raise RuntimeError('Linked improvement proposal is missing.')
        if improvement.status != ProposalStatus.DEPLOYED:
            raise RuntimeError(
                f'Linked improvement is {improvement.status.value}; skill activation requires DEPLOYED.'
            )
        evidence = self._verify_files(skill)
        skill.status = SkillProposalStatus.ACTIVE
        self.registry.save(skill)
        return {
            'ok': True,
            'skill_id': skill.id,
            'slug': skill.manifest.slug,
            'status': skill.status.value,
            'improvement_proposal_id': improvement.id,
            'verification': evidence,
        }

    def disable(self, skill_id: str, *, explicit_user_approval: bool) -> dict:
        if not explicit_user_approval:
            raise PermissionError('Explicit skill disable approval is required.')
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(skill_id)
        skill.status = SkillProposalStatus.DISABLED
        self.registry.save(skill)
        return {'ok': True, 'skill_id': skill.id, 'status': skill.status.value}
