from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .policy import ApprovalDecision


COLORS = {
    'LOW': '#6affb8',
    'MEDIUM': '#ffd166',
    'HIGH': '#ff9f5b',
    'CRITICAL': '#ff5c73',
}


def ask_approval(parent: tk.Misc, tool_name: str, payload: dict) -> str:
    """Show explicit action/risk/target details and return an ApprovalDecision value."""
    info = payload.get('__approval__', {}) if isinstance(payload, dict) else {}
    arguments = payload.get('arguments', {}) if isinstance(payload, dict) else {}
    result = {'decision': ApprovalDecision.DENY.value}

    window = tk.Toplevel(parent)
    window.title('JARVIS V7 // APPROVAL CENTER')
    window.configure(bg='#06111b')
    window.transient(parent)
    window.grab_set()
    window.resizable(True, True)
    window.geometry('650x600')
    window.minsize(560, 480)

    risk = str(info.get('risk', 'HIGH')).upper()
    accent = COLORS.get(risk, COLORS['HIGH'])

    header = tk.Frame(window, bg='#061725', padx=18, pady=14)
    header.pack(fill='x')
    tk.Label(
        header, text='J A R V I S   V7  //  APPROVAL CENTER',
        bg='#061725', fg='#53e7ff', font=('Segoe UI', 15, 'bold'),
    ).pack(anchor='w')
    tk.Label(
        header, text='Review the exact action before JARVIS is allowed to continue.',
        bg='#061725', fg='#8bb7c8', font=('Segoe UI', 9),
    ).pack(anchor='w', pady=(3, 0))

    body = tk.Frame(window, bg='#06111b', padx=18, pady=14)
    body.pack(fill='both', expand=True)

    def row(label: str, value: str, color: str = '#e7f7ff') -> None:
        tk.Label(body, text=label, bg='#06111b', fg='#8bb7c8', font=('Consolas', 9, 'bold')).pack(anchor='w')
        tk.Label(
            body, text=value or '—', bg='#091b27', fg=color, font=('Segoe UI', 10),
            justify='left', anchor='w', wraplength=585, padx=10, pady=7,
        ).pack(fill='x', pady=(2, 9))

    row('ACTION', str(info.get('action') or tool_name))
    row('TARGET', str(info.get('target') or 'local JARVIS runtime'))
    row('RISK', risk, accent)
    row('WHY', str(info.get('why') or 'This action requires explicit permission.'))
    caps = ', '.join(str(item) for item in info.get('capabilities', [])) or 'Unclassified'
    row('CAPABILITIES', caps)

    tk.Label(body, text='ARGUMENT SUMMARY', bg='#06111b', fg='#8bb7c8', font=('Consolas', 9, 'bold')).pack(anchor='w')
    tree = ttk.Treeview(body, columns=('value',), show='tree headings', height=6)
    tree.heading('#0', text='Field')
    tree.heading('value', text='Value')
    tree.column('#0', width=150, anchor='w')
    tree.column('value', width=400, anchor='w')
    for key, value in arguments.items():
        tree.insert('', 'end', text=str(key), values=(str(value),))
    tree.pack(fill='both', expand=True, pady=(3, 12))

    note = (
        'ALLOW FOR SESSION never disables ALWAYS_ASK policies such as EMAIL_SEND or CALENDAR_WRITE. '
        'CANCEL MISSION asks the active mission to stop before future steps.'
    )
    tk.Label(body, text=note, bg='#06111b', fg='#8bb7c8', font=('Segoe UI', 8), wraplength=585, justify='left').pack(anchor='w')

    actions = tk.Frame(window, bg='#061725', padx=12, pady=12)
    actions.pack(fill='x')

    def choose(decision: ApprovalDecision) -> None:
        result['decision'] = decision.value
        try:
            window.grab_release()
        except Exception:
            pass
        window.destroy()

    button_specs = [
        ('ALLOW ONCE', ApprovalDecision.ALLOW_ONCE, '#6affb8'),
        ('ALLOW FOR SESSION', ApprovalDecision.ALLOW_SESSION, '#53e7ff'),
        ('DENY', ApprovalDecision.DENY, '#ffd166'),
        ('CANCEL MISSION', ApprovalDecision.CANCEL_MISSION, '#ff5c73'),
    ]
    for text, decision, color in button_specs:
        tk.Button(
            actions, text=text, command=lambda d=decision: choose(d),
            bg='#0b2a3a', fg=color, activebackground='#12445b', activeforeground='white',
            relief='flat', font=('Segoe UI', 8, 'bold'), padx=10, pady=7,
        ).pack(side='left', expand=True, fill='x', padx=3)

    window.protocol('WM_DELETE_WINDOW', lambda: choose(ApprovalDecision.DENY))
    window.wait_window()
    return result['decision']
