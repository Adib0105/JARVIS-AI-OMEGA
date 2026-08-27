from __future__ import annotations

import threading
from tkinter import messagebox

from . import ui_command_center as ui
from .config import settings
from .self_development.release import ControlledReleaseEngine


class AgentCommandCenter(ui.AgentCommandCenter):
    """Command Center with release and skill features composed by inheritance."""

    def __init__(self, parent, jarvis) -> None:
        super().__init__(parent, jarvis)
        self.title(f'JARVIS {settings.app_version} // AGENT COMMAND CENTER')

    def _canonicalize_widget_text(self, widget) -> None:
        try:
            text = widget.cget('text')
            if isinstance(text, str):
                updated = text.replace('V7.5', settings.app_version).replace('V6', settings.app_version)
                if updated != text:
                    widget.configure(text=updated)
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._canonicalize_widget_text(child)
        except Exception:
            pass

    def _build(self) -> None:
        super()._build()
        self._canonicalize_widget_text(self)
        self._build_release_tab()
        self._build_skills_tab()

    def _background(self, fn, done=None):
        """Canonical-version background runner; no historical dialog branding."""
        def worker():
            try:
                result = fn()
                error = None
            except Exception as exc:
                result = None
                error = exc

            def finish():
                if error is not None:
                    messagebox.showerror(
                        f'JARVIS {settings.app_version}',
                        f'{type(error).__name__}: {error}',
                        parent=self,
                    )
                elif done:
                    done(result)

            try:
                self.after(0, finish)
            except ui.tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _mission_action(self, action: str):
        mission_id = getattr(self.jarvis, 'last_mission_id', None)
        if not mission_id:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'No active/recent mission ID is available.',
                parent=self,
            )
            return
        fn = {
            'pause': self.jarvis.pause_mission,
            'resume': self.jarvis.resume_mission,
            'cancel': self.jarvis.cancel_mission,
        }[action]
        try:
            ok = fn(mission_id)
            self.overall.configure(
                text=f'● MISSION {action.upper()}={ok}',
                fg=ui.GOLD if ok else ui.RED,
            )
        finally:
            self.refresh_missions()

    def _create_selected_proposal(self):
        gap = self._selected_gap()
        if not gap:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select a detected gap first.',
                parent=self,
            )
            return
        self._background(
            lambda: self.jarvis.propose_improvement(gap),
            lambda data: (
                self._refresh_proposals(),
                self._set_text(self.selfdev_detail, ui._pretty(data)),
            ),
        )

    def _prepare_selected_sandbox(self):
        proposal = self._selected_proposal()
        if not proposal:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select a proposal first.',
                parent=self,
            )
            return
        self._background(
            lambda: self.jarvis.prepare_improvement_sandbox(proposal['id']),
            lambda data: (
                self._refresh_proposals(),
                self._set_text(self.selfdev_detail, ui._pretty(data)),
            ),
        )

    def _run_selected_build(self):
        proposal = self._selected_proposal()
        if not proposal:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select a prepared proposal first.',
                parent=self,
            )
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // SANDBOX BUILD',
            'Run bounded AI coding + full tests in the isolated sandbox?\n\n'
            'Production code will NOT be merged.',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.run_self_coding(proposal['id']),
            lambda data: (
                self._refresh_proposals(),
                self._set_text(self.selfdev_detail, ui._pretty(data)),
            ),
        )

    def _approve_selected(self):
        proposal = self._selected_proposal()
        if not proposal:
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // RELEASE APPROVAL',
            'Approve this tested proposal for the later controlled release stage?\n\n'
            'This button does NOT deploy or merge production code.',
            parent=self,
        ):
            return
        try:
            data = self.jarvis.approve_improvement_for_release(
                proposal['id'],
                explicit_user_approval=True,
            )
            self._refresh_proposals()
            self._set_text(self.selfdev_detail, ui._pretty(data))
        except Exception as exc:
            messagebox.showerror(
                f'JARVIS {settings.app_version}',
                f'{type(exc).__name__}: {exc}',
                parent=self,
            )

    def refresh_all(self):
        super().refresh_all()
        try:
            self._refresh_release_status()
        except Exception:
            pass
        try:
            self._refresh_skills()
        except Exception:
            pass

    # ---- Controlled release ----
    def _build_release_tab(self) -> None:
        frame = self._tab('RELEASE')
        controls = ui.tk.Frame(frame, bg=ui.BG)
        controls.pack(fill='x', pady=10)
        self._button(controls, 'DEPLOY APPROVED', self._deploy_selected_release, ui.RED).pack(side='left', padx=4)
        self._button(controls, 'ROLLBACK DEPLOYMENT', self._rollback_selected_release, ui.GOLD).pack(side='left', padx=4)
        self._button(controls, 'REFRESH RELEASE STATUS', self._refresh_release_status, ui.CYAN).pack(side='left', padx=4)
        self.release_text = self._text(frame)
        self.release_text.pack(fill='both', expand=True, padx=4, pady=8)

    def _release_engine(self):
        return ControlledReleaseEngine(self.jarvis._get_self_development_engine())

    def _refresh_release_status(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        payload = {
            'application_version': settings.app_version,
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

    def _deploy_selected_release(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        if not proposal:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select an APPROVED proposal in SELF DEVELOPMENT first.',
                parent=self,
            )
            return
        if proposal.get('status') != 'APPROVED':
            messagebox.showwarning(
                f'JARVIS {settings.app_version}',
                f"Proposal status is {proposal.get('status')}; APPROVED is required.",
                parent=self,
            )
            return
        if not settings.production_self_modification:
            messagebox.showwarning(
                f'JARVIS {settings.app_version} // PRODUCTION LOCKED',
                'Production self-modification is OFF. This is the safe default.\n\n'
                'Set PRODUCTION_SELF_MODIFICATION=true deliberately in .env only when you want the reviewed release engine enabled.',
                parent=self,
            )
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // DEPLOY APPROVED CHANGE',
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

    def _rollback_selected_release(self):
        proposal = self._selected_proposal() if hasattr(self, '_selected_proposal') else None
        if not proposal:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select a deployed proposal first.',
                parent=self,
            )
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // ROLLBACK',
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

    # ---- Skill lifecycle ----
    def _build_skills_tab(self) -> None:
        frame = self._tab('SKILLS')
        controls = ui.tk.Frame(frame, bg=ui.BG)
        controls.pack(fill='x', pady=8)
        self._button(controls, 'REFRESH', self._refresh_skills, ui.CYAN).pack(side='left', padx=3)
        self._button(controls, 'CREATE FROM GAP', self._create_skill_from_gap, ui.PURPLE).pack(side='left', padx=3)
        self._button(controls, 'PREPARE SANDBOX', self._prepare_skill, ui.GOLD).pack(side='left', padx=3)
        self._button(controls, 'BUILD / TEST', self._build_skill, ui.GOLD).pack(side='left', padx=3)
        self._button(controls, 'ACTIVATE DEPLOYED', self._activate_skill, ui.GREEN).pack(side='left', padx=3)
        self._button(controls, 'DISABLE', self._disable_skill, ui.RED).pack(side='left', padx=3)

        self.skill_list = ui.tk.Listbox(
            frame,
            bg='#071a25',
            fg=ui.TEXT,
            selectbackground='#315c5f',
            relief='flat',
            font=('Consolas', 9),
            height=12,
        )
        self.skill_list.pack(fill='x', padx=4, pady=4)
        self.skill_list.bind('<<ListboxSelect>>', lambda _e: self._show_skill())
        self.skill_detail = self._text(frame)
        self.skill_detail.pack(fill='both', expand=True, padx=4, pady=6)
        self._skill_cache: list[dict] = []

    def _selected_skill(self):
        selected = self.skill_list.curselection()
        return self._skill_cache[selected[0]] if selected else None

    def _refresh_skills(self):
        self._skill_cache = self.jarvis.skill_proposals(200)
        self.skill_list.delete(0, 'end')
        for item in self._skill_cache:
            manifest = item.get('manifest') or {}
            self.skill_list.insert(
                'end',
                f"[{item.get('status')}] {item.get('id')} :: {manifest.get('name', manifest.get('slug', 'skill'))}",
            )
        if self._skill_cache:
            self.skill_list.selection_set(0)
            self._show_skill()

    def _show_skill(self):
        skill = self._selected_skill()
        if skill:
            self._set_text(self.skill_detail, ui._pretty(skill))

    def _create_skill_from_gap(self):
        gap = self._selected_gap() if hasattr(self, '_selected_gap') else None
        if not gap:
            messagebox.showinfo(
                f'JARVIS {settings.app_version}',
                'Select a capability gap in SELF DEVELOPMENT first.',
                parent=self,
            )
            return
        try:
            result = self.jarvis.propose_skill_from_gap(gap)
            self._refresh_skills()
            self._set_text(self.skill_detail, ui._pretty(result))
        except Exception as exc:
            messagebox.showerror(
                f'JARVIS {settings.app_version}',
                f'{type(exc).__name__}: {exc}',
                parent=self,
            )

    def _prepare_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        self._background(
            lambda: self.jarvis.prepare_skill_build(skill['id']),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def _build_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // SKILL BUILD',
            'Run bounded AI coding and the full regression/security suite inside the isolated skill sandbox?\n\n'
            'This does not activate or deploy the skill.',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.run_skill_build(skill['id']),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def _activate_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version} // ACTIVATE SKILL',
            'Activate this skill only if its linked improvement is already DEPLOYED and evaluation metadata is PASS/VERIFIED?',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.activate_skill(skill['id'], explicit_user_approval=True),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def _disable_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno(
            f'JARVIS {settings.app_version}',
            'Disable this active skill?',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.disable_skill(skill['id'], explicit_user_approval=True),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )


def show_command_center(parent, jarvis):
    existing = getattr(parent, '_jarvis_command_center', None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return existing
    except Exception:
        pass
    window = AgentCommandCenter(parent, jarvis)
    try:
        parent._jarvis_command_center = window
    except Exception:
        pass
    return window


__all__ = ['AgentCommandCenter', 'show_command_center']
