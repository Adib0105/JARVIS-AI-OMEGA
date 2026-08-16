from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .storage import BackupManager


BG = '#06131d'
PANEL = '#0a2230'
PANEL2 = '#0d2d3d'
CYAN = '#42e8ff'
GREEN = '#55ffbf'
GOLD = '#ffd34d'
RED = '#ff4d6d'
PURPLE = '#df70ff'
TEXT = '#d8f7ff'
MUTED = '#78a9b8'


def _pretty(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


class AgentCommandCenter(tk.Toplevel):
    """Operator-facing V7.5 mission/health/security/self-development dashboard."""

    def __init__(self, parent, jarvis) -> None:
        super().__init__(parent)
        self.jarvis = jarvis
        self.title('JARVIS V7.5 // AGENT COMMAND CENTER')
        self.configure(bg=BG)
        self.geometry('1180x720')
        self.minsize(980, 620)
        self.transient(parent)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self._gap_cache: list[dict] = []
        self._proposal_cache: list[dict] = []
        self._build()
        self.refresh_all()

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill='x', padx=14, pady=(12, 8))
        tk.Label(
            header, text='J A R V I S   V7.5  //  AGENT COMMAND CENTER',
            bg=BG, fg=CYAN, font=('Consolas', 16, 'bold'),
        ).pack(side='left')
        self.overall = tk.Label(header, text='● REFRESHING', bg=BG, fg=GOLD, font=('Consolas', 10, 'bold'))
        self.overall.pack(side='right', padx=8)
        tk.Button(
            header, text='REFRESH ALL', command=self.refresh_all, bg=PANEL2, fg=CYAN,
            activebackground=PANEL, activeforeground='white', relief='flat', font=('Segoe UI', 9, 'bold'), padx=12,
        ).pack(side='right')

        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Jarvis.TNotebook', background=BG, borderwidth=0)
        style.configure('Jarvis.TNotebook.Tab', background=PANEL, foreground=TEXT, padding=(12, 7), font=('Segoe UI', 9, 'bold'))
        style.map('Jarvis.TNotebook.Tab', background=[('selected', PANEL2)], foreground=[('selected', CYAN)])
        style.configure('Jarvis.Treeview', background='#071a25', fieldbackground='#071a25', foreground=TEXT, rowheight=24, borderwidth=0)
        style.configure('Jarvis.Treeview.Heading', background=PANEL2, foreground=CYAN, relief='flat', font=('Segoe UI', 9, 'bold'))
        style.map('Jarvis.Treeview', background=[('selected', '#0d4055')])

        self.tabs = ttk.Notebook(self, style='Jarvis.TNotebook')
        self.tabs.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        self._build_missions()
        self._build_health()
        self._build_capabilities()
        self._build_observability()
        self._build_security()
        self._build_self_development()
        self._build_data()

    def _tab(self, title: str) -> tk.Frame:
        frame = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(frame, text=title)
        return frame

    def _text(self, parent) -> tk.Text:
        widget = tk.Text(
            parent, bg='#071a25', fg=TEXT, insertbackground=CYAN,
            relief='flat', font=('Consolas', 9), wrap='word', padx=10, pady=8,
        )
        widget.configure(state='disabled')
        return widget

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', value)
        widget.configure(state='disabled')

    def _button(self, parent, text, command, color=CYAN):
        return tk.Button(
            parent, text=text, command=command, bg=PANEL2, fg=color,
            activebackground='#15506a', activeforeground='white', relief='flat',
            font=('Segoe UI', 8, 'bold'), padx=9, pady=5,
        )

    def _background(self, fn, done=None):
        def worker():
            try:
                result = fn()
                error = None
            except Exception as exc:
                result = None
                error = exc
            def finish():
                if error is not None:
                    messagebox.showerror('JARVIS V7.5', f'{type(error).__name__}: {error}', parent=self)
                elif done:
                    done(result)
            try:
                self.after(0, finish)
            except tk.TclError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    # ---- Mission Dashboard ----
    def _build_missions(self):
        frame = self._tab('MISSION')
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill='x', pady=8)
        self._button(controls, 'PAUSE ACTIVE', lambda: self._mission_action('pause'), GOLD).pack(side='left', padx=4)
        self._button(controls, 'RESUME ACTIVE', lambda: self._mission_action('resume'), GREEN).pack(side='left', padx=4)
        self._button(controls, 'CANCEL ACTIVE', lambda: self._mission_action('cancel'), RED).pack(side='left', padx=4)
        self._button(controls, 'REFRESH', self.refresh_missions).pack(side='left', padx=4)

        self.mission_tree = ttk.Treeview(frame, columns=('status', 'goal', 'updated'), show='headings', style='Jarvis.Treeview', height=10)
        for name, width in (('status', 130), ('goal', 650), ('updated', 200)):
            self.mission_tree.heading(name, text=name.upper())
            self.mission_tree.column(name, width=width, anchor='w')
        self.mission_tree.pack(fill='x', padx=4)
        self.mission_tree.bind('<<TreeviewSelect>>', lambda _e: self._show_mission())
        self.mission_detail = self._text(frame)
        self.mission_detail.pack(fill='both', expand=True, padx=4, pady=8)

    def _mission_action(self, action: str):
        mission_id = getattr(self.jarvis, 'last_mission_id', None)
        if not mission_id:
            messagebox.showinfo('JARVIS V7.5', 'No active/recent mission ID is available.', parent=self)
            return
        fn = {'pause': self.jarvis.pause_mission, 'resume': self.jarvis.resume_mission, 'cancel': self.jarvis.cancel_mission}[action]
        try:
            ok = fn(mission_id)
            self.overall.configure(text=f'● MISSION {action.upper()}={ok}', fg=GOLD if ok else RED)
        finally:
            self.refresh_missions()

    def refresh_missions(self):
        rows = self.jarvis.recent_missions(50)
        self.mission_tree.delete(*self.mission_tree.get_children())
        for row in rows:
            self.mission_tree.insert('', 'end', iid=str(row['id']), values=(row.get('status'), row.get('goal'), row.get('updated_at')))
        if rows:
            first = str(rows[0]['id'])
            self.mission_tree.selection_set(first)
            self._show_mission()

    def _show_mission(self):
        selected = self.mission_tree.selection()
        if not selected:
            return
        mission = self.jarvis.get_mission(selected[0])
        if mission is None:
            return
        payload = {
            'id': mission.id,
            'goal': mission.goal,
            'status': mission.status.value,
            'current_step': mission.current_step,
            'retry_count': mission.retry_count,
            'recovery_count': mission.recovery_count,
            'last_error': mission.last_error,
            'steps': [step.as_dict() for step in mission.steps],
            'verification': mission.final_verification.as_dict() if mission.final_verification else None,
            'final_report': mission.final_report,
        }
        self._set_text(self.mission_detail, _pretty(payload))

    # ---- Health ----
    def _build_health(self):
        frame = self._tab('HEALTH')
        top = tk.Frame(frame, bg=BG); top.pack(fill='x', pady=8)
        self.health_label = tk.Label(top, text='HEALTH: —', bg=BG, fg=CYAN, font=('Consolas', 13, 'bold'))
        self.health_label.pack(side='left', padx=6)
        self._button(top, 'RUN HEALTH CHECK', self.refresh_health).pack(side='right', padx=4)
        self.health_tree = ttk.Treeview(frame, columns=('status', 'check', 'detail'), show='headings', style='Jarvis.Treeview')
        for name, width in (('status', 90), ('check', 220), ('detail', 720)):
            self.health_tree.heading(name, text=name.upper()); self.health_tree.column(name, width=width, anchor='w')
        self.health_tree.pack(fill='both', expand=True, padx=4, pady=4)

    def refresh_health(self):
        report = self.jarvis.health_check()
        status = report['status']
        color = GREEN if status == 'PASS' else GOLD if status == 'WARNING' else RED
        self.health_label.configure(text=f'HEALTH: {status}', fg=color)
        self.health_tree.delete(*self.health_tree.get_children())
        for item in report['checks']:
            self.health_tree.insert('', 'end', values=(item['status'], item['name'], item['detail']))

    # ---- Capabilities ----
    def _build_capabilities(self):
        frame = self._tab('CAPABILITIES')
        top = tk.Frame(frame, bg=BG); top.pack(fill='x', pady=8)
        self._button(top, 'REFRESH REGISTRY', self.refresh_capabilities).pack(side='right', padx=4)
        self.cap_tree = ttk.Treeview(frame, columns=('status', 'name', 'risk', 'detail'), show='headings', style='Jarvis.Treeview')
        for name, width in (('status', 110), ('name', 190), ('risk', 90), ('detail', 690)):
            self.cap_tree.heading(name, text=name.upper()); self.cap_tree.column(name, width=width, anchor='w')
        self.cap_tree.pack(fill='both', expand=True, padx=4, pady=4)

    def refresh_capabilities(self):
        self.cap_tree.delete(*self.cap_tree.get_children())
        for item in self.jarvis.capability_status():
            self.cap_tree.insert('', 'end', values=(item['status'], item['name'], item['risk'], item.get('detail', '')))

    # ---- Observability / Cost ----
    def _build_observability(self):
        frame = self._tab('OBSERVABILITY')
        top = tk.Frame(frame, bg=BG); top.pack(fill='x', pady=8)
        self._button(top, 'REFRESH USAGE', self.refresh_observability).pack(side='right', padx=4)
        self.obs_text = self._text(frame); self.obs_text.pack(fill='both', expand=True, padx=4, pady=4)

    def refresh_observability(self):
        data = {
            'today': self.jarvis.model_usage('today'),
            'week': self.jarvis.model_usage('week'),
            'month': self.jarvis.model_usage('month'),
            'recent_events': self.jarvis.observability.events(limit=50),
        }
        self._set_text(self.obs_text, _pretty(data))

    # ---- Security ----
    def _build_security(self):
        frame = self._tab('SECURITY')
        top = tk.Frame(frame, bg=BG); top.pack(fill='x', pady=8)
        self._button(top, 'REFRESH AUDIT', self.refresh_security).pack(side='right', padx=4)
        self.security_text = self._text(frame); self.security_text.pack(fill='both', expand=True, padx=4, pady=4)

    def refresh_security(self):
        rows = self.jarvis.tools.audit.list_entries(limit=100)
        blocked = [row for row in rows if row.get('execution_status') in {'DENIED', 'FAILED'} or row.get('approval_status') == 'BLOCKED_SECRET']
        self._set_text(self.security_text, _pretty({
            'trusted_local_mode': __import__('os').getenv('TRUSTED_LOCAL_MODE', 'true'),
            'recent_sensitive_or_blocked': blocked[:30],
            'recent_audit_events': rows[:50],
        }))

    # ---- Self Development ----
    def _build_self_development(self):
        frame = self._tab('SELF DEVELOPMENT')
        controls = tk.Frame(frame, bg=BG); controls.pack(fill='x', pady=8)
        self._button(controls, 'SELF EVALUATE', self._evaluate, GREEN).pack(side='left', padx=3)
        self._button(controls, 'DETECT GAPS', self._detect_gaps, GOLD).pack(side='left', padx=3)
        self._button(controls, 'CREATE PROPOSAL', self._create_selected_proposal, PURPLE).pack(side='left', padx=3)
        self._button(controls, 'PREPARE SANDBOX', self._prepare_selected_sandbox).pack(side='left', padx=3)
        self._button(controls, 'RUN SANDBOX BUILD', self._run_selected_build, GOLD).pack(side='left', padx=3)
        self._button(controls, 'APPROVE FOR RELEASE', self._approve_selected, GREEN).pack(side='left', padx=3)
        self._button(controls, 'REJECT', self._reject_selected, RED).pack(side='left', padx=3)

        body = tk.PanedWindow(frame, orient='horizontal', bg=BG, sashwidth=4)
        body.pack(fill='both', expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG); right = tk.Frame(body, bg=BG)
        body.add(left, minsize=390); body.add(right, minsize=500)
        tk.Label(left, text='DETECTED GAPS', bg=BG, fg=GOLD, font=('Consolas', 10, 'bold')).pack(anchor='w')
        self.gap_list = tk.Listbox(left, bg='#071a25', fg=TEXT, selectbackground='#5c315f', relief='flat', font=('Consolas', 8))
        self.gap_list.pack(fill='both', expand=True, pady=(4, 8))
        self.gap_list.bind('<<ListboxSelect>>', lambda _e: self._show_gap())
        tk.Label(left, text='PROPOSALS', bg=BG, fg=PURPLE, font=('Consolas', 10, 'bold')).pack(anchor='w')
        self.proposal_list = tk.Listbox(left, bg='#071a25', fg=TEXT, selectbackground='#5c315f', relief='flat', font=('Consolas', 8))
        self.proposal_list.pack(fill='both', expand=True, pady=(4, 0))
        self.proposal_list.bind('<<ListboxSelect>>', lambda _e: self._show_proposal())
        self.selfdev_detail = self._text(right); self.selfdev_detail.pack(fill='both', expand=True)

    def _evaluate(self):
        self._background(lambda: self.jarvis.evaluate_self(), lambda data: self._set_text(self.selfdev_detail, _pretty(data)))

    def _detect_gaps(self):
        def done(data):
            self._gap_cache = data
            self.gap_list.delete(0, 'end')
            for item in data:
                self.gap_list.insert('end', f"[{item['severity']}] {item['capability']} :: {item['title']}")
            self._set_text(self.selfdev_detail, _pretty(data))
        self._background(lambda: self.jarvis.detect_capability_gaps(), done)

    def _selected_gap(self):
        selected = self.gap_list.curselection()
        return self._gap_cache[selected[0]] if selected else None

    def _refresh_proposals(self):
        try:
            self._proposal_cache = self.jarvis.self_development_proposals(100)
        except Exception:
            self._proposal_cache = []
        self.proposal_list.delete(0, 'end')
        for item in self._proposal_cache:
            self.proposal_list.insert('end', f"[{item['status']}] {item['id']} :: {item['title']}")

    def _selected_proposal(self):
        selected = self.proposal_list.curselection()
        return self._proposal_cache[selected[0]] if selected else None

    def _create_selected_proposal(self):
        gap = self._selected_gap()
        if not gap:
            messagebox.showinfo('JARVIS V7.5', 'Select a detected gap first.', parent=self); return
        self._background(lambda: self.jarvis.propose_improvement(gap), lambda data: (self._refresh_proposals(), self._set_text(self.selfdev_detail, _pretty(data))))

    def _prepare_selected_sandbox(self):
        proposal = self._selected_proposal()
        if not proposal:
            messagebox.showinfo('JARVIS V7.5', 'Select a proposal first.', parent=self); return
        self._background(lambda: self.jarvis.prepare_improvement_sandbox(proposal['id']), lambda data: (self._refresh_proposals(), self._set_text(self.selfdev_detail, _pretty(data))))

    def _run_selected_build(self):
        proposal = self._selected_proposal()
        if not proposal:
            messagebox.showinfo('JARVIS V7.5', 'Select a prepared proposal first.', parent=self); return
        if not messagebox.askyesno('JARVIS V7.5 // SANDBOX BUILD', 'Run bounded AI coding + full tests in the isolated sandbox?\n\nProduction code will NOT be merged.', parent=self):
            return
        self._background(lambda: self.jarvis.run_self_coding(proposal['id']), lambda data: (self._refresh_proposals(), self._set_text(self.selfdev_detail, _pretty(data))))

    def _approve_selected(self):
        proposal = self._selected_proposal()
        if not proposal:
            return
        if not messagebox.askyesno('JARVIS V7.5 // RELEASE APPROVAL', 'Approve this tested proposal for the later controlled release stage?\n\nThis button does NOT deploy or merge production code.', parent=self):
            return
        try:
            data = self.jarvis.approve_improvement_for_release(proposal['id'], explicit_user_approval=True)
            self._refresh_proposals(); self._set_text(self.selfdev_detail, _pretty(data))
        except Exception as exc:
            messagebox.showerror('JARVIS V7.5', f'{type(exc).__name__}: {exc}', parent=self)

    def _reject_selected(self):
        proposal = self._selected_proposal()
        if proposal:
            data = self.jarvis.reject_improvement(proposal['id'])
            self._refresh_proposals(); self._set_text(self.selfdev_detail, _pretty(data))

    def _show_gap(self):
        gap = self._selected_gap()
        if gap: self._set_text(self.selfdev_detail, _pretty(gap))

    def _show_proposal(self):
        proposal = self._selected_proposal()
        if proposal: self._set_text(self.selfdev_detail, _pretty(proposal))

    # ---- Data / Backup ----
    def _build_data(self):
        frame = self._tab('DATA / BACKUP')
        controls = tk.Frame(frame, bg=BG); controls.pack(fill='x', pady=10)
        self._button(controls, 'BACKUP DATABASE', self._backup, GREEN).pack(side='left', padx=4)
        self._button(controls, 'EXPORT JARVIS DATA', self._export, CYAN).pack(side='left', padx=4)
        self._button(controls, 'RESTORE DATABASE', self._restore, RED).pack(side='left', padx=4)
        self._button(controls, 'IMPORT JARVIS DATA', self._import, RED).pack(side='left', padx=4)
        self.data_text = self._text(frame); self.data_text.pack(fill='both', expand=True, padx=4, pady=8)

    def _backup_manager(self):
        return BackupManager(self.jarvis.memory.db_path)

    def _backup(self):
        self._background(lambda: self._backup_manager().create_backup('manual'), lambda data: self._set_text(self.data_text, _pretty(data)))

    def _export(self):
        target = filedialog.asksaveasfilename(parent=self, defaultextension='.zip', filetypes=[('JARVIS Backup', '*.zip')])
        if target:
            self._background(lambda: self._backup_manager().export_data(target), lambda data: self._set_text(self.data_text, _pretty(data)))

    def _restore(self):
        source = filedialog.askopenfilename(parent=self, filetypes=[('SQLite database', '*.db'), ('All files', '*.*')])
        if not source: return
        if not messagebox.askyesno('DESTRUCTIVE RESTORE', 'Restore this database? A pre-restore backup will be created first.', parent=self): return
        self._background(lambda: self._backup_manager().restore_database(source, explicit_confirmation=True), lambda data: self._set_text(self.data_text, _pretty(data)))

    def _import(self):
        source = filedialog.askopenfilename(parent=self, filetypes=[('JARVIS Backup', '*.zip')])
        if not source: return
        if not messagebox.askyesno('DESTRUCTIVE IMPORT', 'Import this JARVIS data archive? A pre-restore backup will be created first.', parent=self): return
        self._background(lambda: self._backup_manager().import_archive(source, explicit_confirmation=True), lambda data: self._set_text(self.data_text, _pretty(data)))

    def refresh_all(self):
        try: self.refresh_missions()
        except Exception: pass
        try: self.refresh_health()
        except Exception: pass
        try: self.refresh_capabilities()
        except Exception: pass
        try: self.refresh_observability()
        except Exception: pass
        try: self.refresh_security()
        except Exception: pass
        try: self._gap_cache = self.jarvis.capability_gap_history(100)
        except Exception: self._gap_cache = []
        self.gap_list.delete(0, 'end')
        for item in self._gap_cache:
            self.gap_list.insert('end', f"[{item['severity']}] {item['capability']} :: {item['title']}")
        self._refresh_proposals()
        try:
            status = self.jarvis.health_check()['status']
            self.overall.configure(text=f'● {status}', fg=GREEN if status == 'PASS' else GOLD if status == 'WARNING' else RED)
        except Exception:
            self.overall.configure(text='● DEGRADED', fg=RED)


def show_command_center(parent, jarvis):
    existing = getattr(parent, '_jarvis_command_center', None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift(); existing.focus_force(); return existing
    except Exception:
        pass
    window = AgentCommandCenter(parent, jarvis)
    try:
        parent._jarvis_command_center = window
    except Exception:
        pass
    return window
