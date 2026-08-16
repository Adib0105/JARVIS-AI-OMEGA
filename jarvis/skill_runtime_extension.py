from __future__ import annotations


def install_skill_runtime() -> None:
    """Attach guarded skill lifecycle APIs to the public JarvisOmega runtime."""
    from .core import JarvisOmega
    if getattr(JarvisOmega, '_v75_skill_runtime_installed', False):
        return

    def skill_build_engine(self):
        from .skills.builder import SkillBuildEngine

        development = self._get_self_development_engine()

        def reasoner(system: str, user: str) -> str:
            return self._one_shot_text(system, user, 'coding')

        return SkillBuildEngine(self.skill_registry, development, reasoner)

    def prepare_skill_build(self, skill_id: str) -> dict:
        result = self._skill_build_engine().prepare(skill_id)
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='skill.sandbox_prepared', status='SUCCESS',
            session_id=self.session_id,
            metadata={'skill_id': skill_id, 'improvement_proposal_id': result['improvement']['id']},
        )
        return result

    def run_skill_build(self, skill_id: str) -> dict:
        result = self._skill_build_engine().build(skill_id)
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='skill.build_completed',
            status=str(result['skill'].get('status', 'UNKNOWN')),
            session_id=self.session_id,
            metadata={
                'skill_id': skill_id,
                'improvement_proposal_id': result['skill'].get('improvement_proposal_id'),
            },
        )
        return result

    def activate_skill(self, skill_id: str, *, explicit_user_approval: bool) -> dict:
        from .skills.activation import SkillActivationEngine
        development = self._get_self_development_engine()
        engine = SkillActivationEngine(
            self.skill_registry,
            development.store,
            repo_root=development.sandbox.repo_root,
        )
        result = engine.activate(skill_id, explicit_user_approval=explicit_user_approval)
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='skill.activated', status='SUCCESS',
            session_id=self.session_id,
            metadata={'skill_id': skill_id, 'slug': result.get('slug')},
        )
        return result

    def disable_skill(self, skill_id: str, *, explicit_user_approval: bool) -> dict:
        from .skills.activation import SkillActivationEngine
        development = self._get_self_development_engine()
        engine = SkillActivationEngine(
            self.skill_registry,
            development.store,
            repo_root=development.sandbox.repo_root,
        )
        result = engine.disable(skill_id, explicit_user_approval=explicit_user_approval)
        self.observability.record(
            category='SELF_DEVELOPMENT', event_type='skill.disabled', status='SUCCESS',
            session_id=self.session_id, metadata={'skill_id': skill_id},
        )
        return result

    JarvisOmega._skill_build_engine = skill_build_engine
    JarvisOmega.prepare_skill_build = prepare_skill_build
    JarvisOmega.run_skill_build = run_skill_build
    JarvisOmega.activate_skill = activate_skill
    JarvisOmega.disable_skill = disable_skill
    JarvisOmega._v75_skill_runtime_installed = True
