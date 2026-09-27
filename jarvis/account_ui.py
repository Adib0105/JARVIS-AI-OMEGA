"""Accessible local account management and optional online billing controls."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

from .config import settings
from datetime import datetime, timezone


def show_account_dialog(desktop):
    from .subscription_client import SubscriptionClient, restore_session
    from .user_profiles import ProfileStore
    win = tk.Toplevel(desktop.root)
    win.title('JARVIS — Account / Subscription')
    win.geometry('640x680')
    tabs = ttk.Notebook(win)
    tabs.pack(fill='both', expand=True, padx=16, pady=16)
    local = ttk.Frame(tabs, padding=16)
    online_shell = ttk.Frame(tabs)
    tabs.add(local, text='Local profile')
    tabs.add(online_shell, text='Online subscription')
    canvas = tk.Canvas(online_shell, highlightthickness=0)
    scroll = ttk.Scrollbar(online_shell, orient='vertical', command=canvas.yview)
    scroll.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    online = ttk.Frame(canvas, padding=16)
    window = canvas.create_window(0, 0, window=online, anchor='nw')
    win.account_tabs = tabs
    win.account_canvas = canvas
    online.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
    replies = queue.Queue()
    busy = [False]
    buttons = []
    status = tk.StringVar(value='Local chat, wake and today’s weather remain available without a paid plan.')
    ttk.Label(win, textvariable=status, wraplength=590, justify='left').pack(fill='x', padx=18, pady=(0, 15))

    def field(parent, label, value='', secret=False):
        ttk.Label(parent, text=label).pack(anchor='w', pady=(8, 2))
        variable = tk.StringVar(value=value)
        ttk.Entry(parent, textvariable=variable, show='•' if secret else '').pack(fill='x')
        return variable

    def run(job, kind='status'):
        if busy[0]:
            return
        busy[0] = True
        for button in buttons:
            button.configure(state='disabled')
        status.set('Working…')
        def worker():
            try:
                replies.put((kind, job(), None))
            except Exception as exc:
                replies.put((kind, None, str(exc)))
        threading.Thread(target=worker, daemon=True, name='jarvis-account').start()

    def button(parent, label, command):
        item = ttk.Button(parent, text=label, command=command)
        item.pack(anchor='w', pady=5)
        buttons.append(item)

    username = os.getenv('JARVIS_ACTIVE_USERNAME', '')
    ttk.Label(local, text='Login ID: ' + (username or 'No local desktop profile'), font=('Segoe UI', 12, 'bold')).pack(anchor='w')
    name = field(local, 'Name used in the wake greeting', settings.user_name)
    current = field(local, 'Current local password', secret=True)
    new = field(local, 'New local password (optional; 8+ characters)', secret=True)
    confirm = field(local, 'Confirm new local password', secret=True)
    remember = tk.BooleanVar(value=True)
    ttk.Checkbutton(local, text='Keep me signed in for Windows background startup', variable=remember).pack(anchor='w', pady=10)

    def save_local():
        if new.get() != confirm.get():
            status.set('New passwords do not match.')
            return
        values = (current.get(), name.get(), new.get() or None, remember.get())
        current.set(''); new.set(''); confirm.set('')
        run(lambda: ProfileStore().update_profile(username, values[0], display_name=values[1], new_password=values[2], remember=values[3]), 'profile')

    button(local, 'Save name / change password', save_local)
    def generate_recovery():
        password_value = current.get()
        current.set('')
        run(lambda: ProfileStore().recovery_codes(username, password_value), 'recovery_codes')
    button(local, 'Generate replacement local recovery codes', generate_recovery)
    button(local, 'Sign out / switch local user', desktop._sign_out)
    ttk.Label(local, text='Saving rechecks your password and rotates the remembered sign-in token. Each local user keeps a separate data folder.', wraplength=540).pack(anchor='w', pady=12)

    if getattr(desktop, '_subscription_client', None) is None:
        desktop._subscription_client = restore_session()
    restored = desktop._subscription_client
    origin = field(online, 'Your JARVIS account server (HTTPS)', restored.origin if restored else os.getenv('JARVIS_ACCOUNT_SERVER', ''))
    email = field(online, 'Online account email')
    password = field(online, 'Online password (12+ characters when creating an account)', secret=True)
    cloud_name = field(online, 'Name for a new online account', settings.user_name)
    cloud_remember = tk.BooleanVar(value=bool(restored and restored.remember))
    use_online_name = tk.BooleanVar(value=bool(restored and restored.use_online_name))
    ttk.Checkbutton(online, text='Remember online sign-in on this Windows account', variable=cloud_remember).pack(anchor='w', pady=4)
    ttk.Checkbutton(online, text='Use signed-in online name for wake greeting', variable=use_online_name).pack(anchor='w', pady=4)
    ttk.Label(online, text='Online identity stays separate from local chat history. Remembered sign-in expires within 7 days. Card entry happens on Stripe’s hosted page.', wraplength=540).pack(anchor='w', pady=8)

    def client():
        cached = getattr(desktop, '_subscription_client', None)
        requested = origin.get().strip().rstrip('/')
        if cached is None or cached.origin != requested:
            replacement = SubscriptionClient(requested)
            if cached is not None:
                cached._token = ''
                cached._persist()
            cached = replacement
            desktop._subscription_client = cached
        return cached

    def login(create=False):
        try:
            api = client()
        except ValueError as exc:
            status.set(str(exc)); return
        values = (email.get(), password.get(), cloud_name.get() if create else None, cloud_remember.get(), use_online_name.get())
        password.set('')
        run(lambda: api.sign_in(values[0], values[1], name=values[2], remember=values[3], use_online_name=values[4]), 'me')

    def action(fn, kind='status'):
        try:
            api = client()
        except ValueError as exc:
            status.set(str(exc)); return
        run(lambda: fn(api), kind)

    button(online, 'Create online account', lambda: login(True))
    button(online, 'Sign in online', login)
    code = field(online, 'Email verification / password reset code', secret=True)
    reset_password = field(online, 'New online password for reset (12+ characters)', secret=True)
    def request_code(kind):
        body = {'email': email.get(), 'kind': kind}
        action(lambda api: api.request('POST', '/auth/request-code', body))
    def verify_code():
        body = {'code': code.get()}
        code.set('')
        action(lambda api: api.request('POST', '/auth/verify-email', body))
    button(online, 'Send email verification code', lambda: request_code('verify'))
    button(online, 'Verify email', lambda: verify_code())
    button(online, 'Forgot online password — send reset code', lambda: request_code('reset'))
    def reset_online():
        values = {'code': code.get(), 'new_password': reset_password.get()}
        code.set(''); reset_password.set('')
        action(lambda api: api.request('POST', '/auth/reset-password', values), 'reset')
    button(online, 'Reset password with code', reset_online)
    button(online, 'Monthly Pro — open checkout', lambda: action(lambda api: api.payment_link('monthly'), 'url'))
    button(online, 'Yearly Pro — open checkout', lambda: action(lambda api: api.payment_link('yearly'), 'url'))
    button(online, 'Manage billing / cancel / invoices', lambda: action(lambda api: api.payment_link(), 'url'))
    button(online, 'Refresh subscription', lambda: action(lambda api: api.request('POST', '/billing/refresh', {}), 'subscription'))
    def weekly():
        location = dict(desktop.background.preferences.get('location') or {})
        if not location:
            status.set('Select your city in Background / Weather first.'); return
        action(lambda api: api.request('POST', '/pro/forecast', location), 'forecast')
    button(online, 'Pro: 7-day forecast for my selected city', weekly)
    button(online, 'Sign out online', lambda: action(lambda api: api.sign_out()))

    def collect():
        if not win.winfo_exists():
            return
        try:
            kind, value, error = replies.get_nowait()
        except queue.Empty:
            win.after(80, collect); return
        busy[0] = False
        for item in buttons:
            item.configure(state='normal')
        if error:
            status.set(error)
        elif kind == 'recovery_codes':
            from tkinter import messagebox
            messagebox.showinfo('Save these codes privately', 'Shown once. Keep offline. Any reset invalidates all remaining codes.\n\n' + '\n'.join(value), parent=win)
            status.set('Recovery codes replaced. Sign in again to restore remembered background startup.')
        elif kind == 'profile':
            value.activate()
            object.__setattr__(settings, 'user_name', value.display_name)
            desktop.operator_label.configure(text='OPERATOR: ' + value.display_name.upper())
            status.set('Profile saved. Your next wake greeting uses ' + value.display_name + '.')
        elif kind == 'url':
            webbrowser.open(value)
            status.set('Payment page opened. Review its price before paying, then Refresh subscription here.')
        elif kind in ('me', 'subscription'):
            desktop.background.weather_next_refresh = 0.0
            sub = value.get('subscription', value)
            def date(value):
                return datetime.fromtimestamp(value, timezone.utc).strftime('%d %b %Y %H:%M UTC') if isinstance(value, (int, float)) and 0 < value < 253402300800 else 'unavailable'
            status.set(f"Plan: {sub.get('plan', 'free')} | Status: {sub.get('status', 'none')} | Ends: {date(sub.get('expires_at'))} | Last checked: {date(sub.get('checked_at'))}")
        elif kind == 'reset':
            client()._token = ''
            client()._persist()
            status.set('Password reset. Sign in again; previous sessions were revoked.')
        elif kind == 'forecast':
            report = str(value.get('report', 'Forecast unavailable.'))
            desktop._append('JARVIS', report)
            desktop.voice.speak(report)
            status.set('7-day forecast added to the conversation.')
        else:
            status.set(value.get('message', 'Done. Refresh account status if needed.') if isinstance(value, dict) else 'Done.')
        win.after(80, collect)
    collect()
    return win
