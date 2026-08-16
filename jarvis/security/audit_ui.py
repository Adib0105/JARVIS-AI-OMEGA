from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .audit import AuditStore


class AuditViewer:
    def __init__(self, parent: tk.Misc, store: AuditStore | None = None) -> None:
        self.store = store or AuditStore()
        self.window = tk.Toplevel(parent)
        self.window.title('JARVIS V7 // AUDIT VIEWER')
        self.window.configure(bg='#06111b')
        self.window.geometry('1100x620')
        self.window.minsize(850, 500)
        self._build()
        self.refresh()

    def _build(self) -> None:
        header = tk.Frame(self.window, bg='#061725', padx=16, pady=12)
        header.pack(fill='x')
        tk.Label(
            header, text='J A R V I S   V7  //  AUDIT VIEWER',
            bg='#061725', fg='#53e7ff', font=('Segoe UI', 15, 'bold'),
        ).pack(side='left')
        tk.Button(
            header, text='REFRESH', command=self.refresh,
            bg='#0b2a3a', fg='#6affb8', relief='flat', padx=12, pady=6,
        ).pack(side='right')

        filters = tk.Frame(self.window, bg='#06111b', padx=14, pady=10)
        filters.pack(fill='x')
        self.status_var = tk.StringVar(value='ALL')
        self.risk_var = tk.BooleanVar(value=False)
        self.tool_var = tk.StringVar(value='')
        self.mission_var = tk.StringVar(value='')

        tk.Label(filters, text='STATUS', bg='#06111b', fg='#8bb7c8').pack(side='left')
        ttk.Combobox(
            filters, textvariable=self.status_var,
            values=('ALL', 'SUCCESS', 'FAILED', 'DENIED'), state='readonly', width=11,
        ).pack(side='left', padx=(5, 12))
        tk.Checkbutton(
            filters, text='HIGH RISK ONLY', variable=self.risk_var,
            bg='#06111b', fg='#ffd166', selectcolor='#091b27', activebackground='#06111b',
        ).pack(side='left', padx=(0, 12))
        tk.Label(filters, text='TOOL', bg='#06111b', fg='#8bb7c8').pack(side='left')
        tk.Entry(filters, textvariable=self.tool_var, width=18, bg='#091b27', fg='white', insertbackground='white').pack(side='left', padx=(5, 12))
        tk.Label(filters, text='MISSION', bg='#06111b', fg='#8bb7c8').pack(side='left')
        tk.Entry(filters, textvariable=self.mission_var, width=18, bg='#091b27', fg='white', insertbackground='white').pack(side='left', padx=(5, 12))
        tk.Button(filters, text='APPLY', command=self.refresh, bg='#0b2a3a', fg='#53e7ff', relief='flat').pack(side='left')

        columns = ('time', 'mission', 'tool', 'risk', 'approval', 'execution', 'verify', 'latency')
        self.tree = ttk.Treeview(self.window, columns=columns, show='headings')
        headings = {
            'time': 'Time', 'mission': 'Mission', 'tool': 'Tool', 'risk': 'Risk',
            'approval': 'Approval', 'execution': 'Execution', 'verify': 'Verification', 'latency': 'Latency ms',
        }
        widths = {'time': 180, 'mission': 130, 'tool': 160, 'risk': 75, 'approval': 125, 'execution': 90, 'verify': 145, 'latency': 90}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor='w')
        self.tree.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        self.tree.bind('<<TreeviewSelect>>', self._show_details)

        self.details = tk.Text(
            self.window, height=7, bg='#04101a', fg='#e7f7ff', relief='flat',
            font=('Consolas', 8), wrap='word', padx=10, pady=8,
        )
        self.details.pack(fill='x', padx=14, pady=(0, 14))
        self._rows: dict[str, dict] = {}

    def refresh(self) -> None:
        status = self.status_var.get().strip().upper()
        rows = self.store.list_entries(
            limit=500,
            mission_id=self.mission_var.get().strip() or None,
            tool_name=self.tool_var.get().strip() or None,
            execution_status=None if status == 'ALL' else status,
            high_risk_only=bool(self.risk_var.get()),
        )
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows.clear()
        for row in rows:
            iid = str(row['id'])
            self._rows[iid] = row
            self.tree.insert('', 'end', iid=iid, values=(
                row.get('timestamp', ''), row.get('mission_id') or '—', row.get('tool_name', ''),
                row.get('risk_level', ''), row.get('approval_status', ''), row.get('execution_status', ''),
                row.get('verification_result') or '—', row.get('latency_ms') if row.get('latency_ms') is not None else '—',
            ))
        self.details.delete('1.0', 'end')
        self.details.insert('end', f'{len(rows)} audit event(s). Raw tool arguments and secrets are not stored here.')

    def _show_details(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        row = self._rows.get(selected[0], {})
        lines = [
            f"Audit ID: {row.get('id')}",
            f"Request: {row.get('request_summary') or '—'}",
            f"Capabilities: {', '.join(row.get('capabilities', [])) or '—'}",
            f"Arguments hash: {row.get('arguments_hash') or '—'}",
            f"Error type: {row.get('error_type') or '—'}",
            f"Provider/model: {row.get('provider') or '—'} / {row.get('model') or '—'}",
        ]
        self.details.delete('1.0', 'end')
        self.details.insert('end', '\n'.join(lines))


def show_audit_viewer(parent: tk.Misc, store: AuditStore | None = None) -> AuditViewer:
    return AuditViewer(parent, store)
