from __future__ import annotations

from tkinter import messagebox

from .config import settings
from .self_development.release import ControlledReleaseEngine


def install_release_ui() -> None:
    """Add a guarded RELEASE tab to the V7.5 Agent Command Center.

    This is a UI integration layer only. It cannot bypass ControlledReleaseEngine:
    production self-modification must be deliberately enabled, the proposal must be
    APPROVED, regression/policy checks must pass, and deployment is fast-forward only.
    """
    from . import ui_command_center as ui

    cls = ui.AgentCommandCenter
    if getattr(cls, '_v75_release_ui_installed', False):
        return

    original_build = cls._build

    def build_with_release(self):
        original_build(self)
        frame = self._tab('RELEASE')
        controls = ui.tk.Frame(frame, bg=ui.BG)
        controls.pack(fill='x', pady=10)
        self._button(controls, 'DEPLOY APPROVED', self._deploy_selected_release, ui.RED).pack(side='left', padx=4)
        self._button(controls, 'ROLLBACK DEPLOYMENT', self._rollback_selected_release, ui.GOLD).pack(side='left', padx=4)
        self._button(controls, 'REFRESH RELEASE STATUS', self._refresh_release_status, ui.CYAN).pack(side='left', padx=4)
        self.release_text = self._text(frame)
        self.release_text.pack(fill='both', expand=True, padx=4, pady=8)
        self._refresh_release_status()

    def release_engine(self):
        return ControlledReleaseEngine(self.jarvis._get_self_development_engine())

    def refresh_release_status(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        payload = {
            'production_self_modification': bool(settings.production_self_modification),
            'require_approval_for_production': bool(settings.require_approval_for_production),
            'auto_rollback_enabled': bool(settings.auto_rollback_enabled),
            'selected_proposal': proposal,
            'policy': (
                'Production deployment is disabled by default. A deployment requires an APPROVED proposal, '
                'clean/unchanged production HEAD, pre-release regression PASS, policy PASS, fast-forward-only merge, '
                'post-release regression, and explicit operator confirmation.'
            ),
        }
        self._set_text(self.release_text, ui._pretty(payload))

    def deploy_selected(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        if not proposal:
            messagebox.showinfo('JARVIS V7.5', 'Select an APPROVED proposal in SELF DEVELOPMENT first.', parent=self)
            return
        if proposal.get('status') != 'APPROVED':
            messagebox.showwarning('JARVIS V7.5', f"Proposal status is {proposal.get('status')}; APPROVED is required.", parent=self)
            return
        if not settings.production_self_modification:
            messagebox.showwarning(
                'JARVIS V7.5 // PRODUCTION LOCKED',
                'Production self-modification is OFF. This is the safe default.\n\n'
                'Set PRODUCTION_SELF_MODIFICATION=true deliberately in .env only when you want the reviewed release engine enabled.',
                parent=self,
            )
            return
        if not messagebox.askyesno(
            'JARVIS V7.5 // DEPLOY APPROVED CHANGE',
            'Deploy this reviewed proposal to the current production branch?\n\n'
            'JARVIS will re-run regression tests and policy checks before touching production. '
            'The merge is fast-forward only. Continue?',
            parent=self,
        ):
            return

        proposal_id = proposal['id']

        def run():
            return self._release_engine().deploy(
                proposal_id,
                explicit_user_approval=True,
                auto_rollback=settings.auto_rollback_enabled,
            )

        def done(data):
            self._refresh_proposals()
            self._set_text(self.release_text, ui._pretty(data))

        self._background(run, done)

    def rollback_selected(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        if not proposal:
            messagebox.showinfo('JARVIS V7.5', 'Select a deployed proposal first.', parent=self)
            return
        if not messagebox.askyesno(
            'JARVIS V7.5 // ROLLBACK',
            'Create a history-preserving Git revert for the selected deployed improvement and re-run the full regression suite?',
            parent=self,
        ):
            return
        proposal_id = proposal['id']

        def run():
            return self._release_engine().rollback(proposal_id, explicit_confirmation=True)

        def done(data):
            self._refresh_proposals()
            self._set_text(self.release_text, ui._pretty(data))

        self._background(run, done)

    cls._build = build_with_release
    cls._release_engine = release_engine
    cls._refresh_release_status = refresh_release_status
    cls._deploy_selected_release = deploy_selected
    cls._rollback_selected_release = rollback_selected
    cls._v75_release_ui_installed = True
