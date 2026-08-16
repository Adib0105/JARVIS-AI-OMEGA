from __future__ import annotations

from tkinter import messagebox


def install_skill_ui() -> None:
    from . import ui_command_center as ui

    cls = ui.AgentCommandCenter
    if getattr(cls, '_v75_skill_ui_installed', False):
        return

    original_build = cls._build

    def build_with_skills(self):
        original_build(self)
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
            frame, bg='#071a25', fg=ui.TEXT, selectbackground='#315c5f',
            relief='flat', font=('Consolas', 9), height=12,
        )
        self.skill_list.pack(fill='x', padx=4, pady=4)
        self.skill_list.bind('<<ListboxSelect>>', lambda _e: self._show_skill())
        self.skill_detail = self._text(frame)
        self.skill_detail.pack(fill='both', expand=True, padx=4, pady=6)
        self._skill_cache = []
        self._refresh_skills()

    def selected_skill(self):
        selected = self.skill_list.curselection()
        return self._skill_cache[selected[0]] if selected else None

    def refresh_skills(self):
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

    def show_skill(self):
        skill = self._selected_skill()
        if skill:
            self._set_text(self.skill_detail, ui._pretty(skill))

    def create_skill_from_gap(self):
        gap = self._selected_gap() if hasattr(self, '_selected_gap') else None
        if not gap:
            messagebox.showinfo('JARVIS V7.5', 'Select a capability gap in SELF DEVELOPMENT first.', parent=self)
            return
        try:
            result = self.jarvis.propose_skill_from_gap(gap)
            self._refresh_skills()
            self._set_text(self.skill_detail, ui._pretty(result))
        except Exception as exc:
            messagebox.showerror('JARVIS V7.5', f'{type(exc).__name__}: {exc}', parent=self)

    def prepare_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        self._background(
            lambda: self.jarvis.prepare_skill_build(skill['id']),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def build_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno(
            'JARVIS V7.5 // SKILL BUILD',
            'Run bounded AI coding and the full regression/security suite inside the isolated skill sandbox?\n\n'
            'This does not activate or deploy the skill.',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.run_skill_build(skill['id']),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def activate_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno(
            'JARVIS V7.5 // ACTIVATE SKILL',
            'Activate this skill only if its linked improvement is already DEPLOYED and evaluation metadata is PASS/VERIFIED?',
            parent=self,
        ):
            return
        self._background(
            lambda: self.jarvis.activate_skill(skill['id'], explicit_user_approval=True),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    def disable_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        if not messagebox.askyesno('JARVIS V7.5', 'Disable this active skill?', parent=self):
            return
        self._background(
            lambda: self.jarvis.disable_skill(skill['id'], explicit_user_approval=True),
            lambda data: (self._refresh_skills(), self._set_text(self.skill_detail, ui._pretty(data))),
        )

    cls._build = build_with_skills
    cls._selected_skill = selected_skill
    cls._refresh_skills = refresh_skills
    cls._show_skill = show_skill
    cls._create_skill_from_gap = create_skill_from_gap
    cls._prepare_skill = prepare_skill
    cls._build_skill = build_skill
    cls._activate_skill = activate_skill
    cls._disable_skill = disable_skill
    cls._v75_skill_ui_installed = True
