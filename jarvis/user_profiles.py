"""Local multi-user sign-in for the Windows desktop application.

Passwords never leave the computer and are never stored.  The account file
contains salted PBKDF2 digests; a random remembered-session token enables the
background startup shortcut to launch without displaying a login window at
every Windows sign-in.

This is a local product/account foundation, not a cloud subscription or payment
system.  Server-side licensing still requires a separately secured backend.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1
PBKDF2_ITERATIONS = 390_000
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_FAILURES = 5
LOCK_SECONDS = 30
_USERNAME = re.compile(r'^[a-z0-9][a-z0-9._-]{2,31}$')


def account_root() -> Path:
    configured = os.getenv('JARVIS_ACCOUNT_ROOT', '').strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == 'nt' and os.getenv('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'JARVIS-AI-OMEGA'
    return Path.home() / '.jarvis-ai-omega'


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=path.parent, delete=False
        ) as stream:
            temp_path = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
        try:
            temp_path.chmod(0o600)
        except OSError:
            pass
        temp_path.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii')


def _decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw.encode('ascii'))


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS, dklen=32
    )


def _clean_username(username: str) -> str:
    value = str(username or '').strip().lower()
    if not _USERNAME.fullmatch(value):
        raise ValueError('Login ID must be 3–32 characters: letters, numbers, dot, dash or underscore.')
    return value


def _clean_display_name(display_name: str) -> str:
    value = ' '.join(str(display_name or '').strip().split())
    if not 1 <= len(value) <= 60 or any(ch in value for ch in '\r\n\0'):
        raise ValueError('Name must contain 1–60 ordinary characters.')
    return value


def _validate_password(password: str) -> str:
    value = str(password or '')
    if not 8 <= len(value) <= 256:
        raise ValueError('Password must contain 8–256 characters.')
    if '\0' in value:
        raise ValueError('Password contains an invalid character.')
    return value


@dataclass(frozen=True)
class ActiveProfile:
    profile_id: str
    username: str
    display_name: str
    data_dir: Path

    def activate(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        os.environ['JARVIS_ACTIVE_PROFILE_ID'] = self.profile_id
        os.environ['JARVIS_ACTIVE_USERNAME'] = self.username
        os.environ['JARVIS_ACTIVE_DISPLAY_NAME'] = self.display_name
        os.environ['JARVIS_ACTIVE_DATA_DIR'] = str(self.data_dir)


class ProfileStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else account_root()
        self.accounts_path = self.root / 'accounts.json'
        self.session_path = self.root / 'session.json'
        self._lock = threading.RLock()

    def _empty(self) -> dict:
        return {'schema': SCHEMA_VERSION, 'accounts': {}}

    def _load(self) -> dict:
        try:
            data = json.loads(self.accounts_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return self._empty()
        except (OSError, ValueError, UnicodeError) as exc:
            raise RuntimeError('Local account store is unreadable. Restore or rename accounts.json.') from exc
        if not isinstance(data, dict) or data.get('schema') != SCHEMA_VERSION or not isinstance(data.get('accounts'), dict):
            raise RuntimeError('Local account store has an unsupported format.')
        return data

    @staticmethod
    def _profile(account: dict) -> ActiveProfile:
        return ActiveProfile(
            profile_id=str(account['id']),
            username=str(account['username']),
            display_name=str(account['display_name']),
            data_dir=Path(str(account['data_dir'])),
        )

    def has_accounts(self) -> bool:
        with self._lock:
            return bool(self._load()['accounts'])

    def usernames(self) -> list[str]:
        with self._lock:
            return sorted(self._load()['accounts'])

    def create(
        self,
        username: str,
        display_name: str,
        password: str,
        *,
        legacy_data_dir: Path | None = None,
        remember: bool = True,
    ) -> ActiveProfile:
        username = _clean_username(username)
        display_name = _clean_display_name(display_name)
        password = _validate_password(password)
        with self._lock:
            data = self._load()
            accounts = data['accounts']
            if username in accounts:
                raise ValueError('This Login ID already exists.')
            profile_id = uuid.uuid4().hex
            legacy = Path(legacy_data_dir) if legacy_data_dir is not None else None
            use_legacy = not accounts and legacy is not None and legacy.exists() and any(legacy.iterdir())
            data_dir = legacy.resolve() if use_legacy else (self.root / 'users' / profile_id).resolve()
            data_dir.mkdir(parents=True, exist_ok=True)
            salt = secrets.token_bytes(16)
            now = int(time.time())
            account = {
                'id': profile_id,
                'username': username,
                'display_name': display_name,
                'data_dir': str(data_dir),
                'password_salt': _encode(salt),
                'password_digest': _encode(_password_digest(password, salt)),
                'created_at': now,
                'failed_attempts': 0,
                'locked_until': 0,
                'session_digest': '',
                'session_expires_at': 0,
            }
            accounts[username] = account
            _atomic_json(self.accounts_path, data)
            profile = self._profile(account)
            if remember:
                self._create_session_locked(data, account)
            return profile

    def authenticate(self, username: str, password: str, *, remember: bool = True) -> ActiveProfile:
        username = _clean_username(username)
        password = str(password or '')
        with self._lock:
            data = self._load()
            account = data['accounts'].get(username)
            if not isinstance(account, dict):
                # Run a real PBKDF2 operation so a missing account is not an
                # obvious timing oracle on the local login screen.
                _password_digest(password, b'\0' * 16)
                raise PermissionError('Login ID or password is incorrect.')
            now = int(time.time())
            locked_until = int(account.get('locked_until') or 0)
            if locked_until > now:
                raise PermissionError(f'Too many attempts. Try again in {locked_until - now} seconds.')
            try:
                salt = _decode(str(account['password_salt']))
                expected = _decode(str(account['password_digest']))
            except Exception as exc:
                raise RuntimeError('This local account record is damaged.') from exc
            actual = _password_digest(password, salt)
            if not hmac.compare_digest(actual, expected):
                attempts = int(account.get('failed_attempts') or 0) + 1
                account['failed_attempts'] = attempts
                if attempts >= MAX_FAILURES:
                    account['locked_until'] = now + LOCK_SECONDS
                    account['failed_attempts'] = 0
                _atomic_json(self.accounts_path, data)
                raise PermissionError('Login ID or password is incorrect.')
            account['failed_attempts'] = 0
            account['locked_until'] = 0
            _atomic_json(self.accounts_path, data)
            if remember:
                self._create_session_locked(data, account)
            else:
                account['session_digest'] = ''
                account['session_expires_at'] = 0
                _atomic_json(self.accounts_path, data)
                self.session_path.unlink(missing_ok=True)
            return self._profile(account)

    def _create_session_locked(self, data: dict, account: dict) -> None:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        for row in data['accounts'].values():
            if isinstance(row, dict):
                row['session_digest'] = ''
                row['session_expires_at'] = 0
        account['session_digest'] = hashlib.sha256(token.encode('utf-8')).hexdigest()
        account['session_expires_at'] = now + SESSION_TTL_SECONDS
        _atomic_json(self.accounts_path, data)
        _atomic_json(self.session_path, {
            'schema': SCHEMA_VERSION,
            'username': account['username'],
            'token': token,
            'created_at': now,
        })

    def resume_session(self) -> ActiveProfile | None:
        with self._lock:
            try:
                session = json.loads(self.session_path.read_text(encoding='utf-8'))
            except (FileNotFoundError, OSError, ValueError, UnicodeError):
                return None
            if not isinstance(session, dict) or session.get('schema') != SCHEMA_VERSION:
                return None
            data = self._load()
            account = data['accounts'].get(str(session.get('username', '')).lower())
            if not isinstance(account, dict):
                return None
            if int(account.get('session_expires_at') or 0) <= int(time.time()):
                self.sign_out()
                return None
            token = str(session.get('token') or '')
            actual = hashlib.sha256(token.encode('utf-8')).hexdigest()
            if not token or not hmac.compare_digest(actual, str(account.get('session_digest') or '')):
                self.sign_out()
                return None
            return self._profile(account)

    def sign_out(self) -> None:
        with self._lock:
            data = self._load()
            changed = False
            for account in data['accounts'].values():
                if isinstance(account, dict) and (account.get('session_digest') or account.get('session_expires_at')):
                    account['session_digest'] = ''
                    account['session_expires_at'] = 0
                    changed = True
            if changed:
                _atomic_json(self.accounts_path, data)
            self.session_path.unlink(missing_ok=True)


def authenticate_desktop(*, legacy_data_dir: Path | None = None, background: bool = False) -> ActiveProfile | None:
    """Resume a remembered profile or show a first-run/login window."""
    store = ProfileStore()
    resumed = store.resume_session()
    if resumed is not None:
        resumed.activate()
        return resumed

    import tkinter as tk
    result: dict[str, ActiveProfile | None] = {'profile': None}
    root = tk.Tk()
    root.title('JARVIS AI OMEGA // SIGN IN')
    root.geometry('500x570')
    root.resizable(False, False)
    root.configure(bg='#06111a')
    root.protocol('WM_DELETE_WINDOW', root.destroy)
    mode = {'create': not store.has_accounts()}

    body = tk.Frame(root, bg='#06111a', padx=34, pady=26)
    body.pack(fill='both', expand=True)

    def render() -> None:
        for child in body.winfo_children():
            child.destroy()
        creating = mode['create']
        tk.Label(body, text='J A R V I S   O M E G A', bg='#06111a', fg='#53e7ff', font=('Segoe UI', 17, 'bold')).pack(pady=(5, 4))
        tk.Label(
            body,
            text=('CREATE YOUR LOCAL PROFILE' if creating else 'WELCOME BACK'),
            bg='#06111a', fg='#6affb8', font=('Consolas', 10, 'bold'),
        ).pack(pady=(0, 18))
        if background:
            tk.Label(body, text='Sign in once so background wake can start.', bg='#06111a', fg='#ffd166').pack(pady=(0, 10))

        display_var = tk.StringVar()
        username_var = tk.StringVar()
        password_var = tk.StringVar()
        confirm_var = tk.StringVar()
        remember_var = tk.BooleanVar(value=True)
        status_var = tk.StringVar()

        def field(label: str, variable, *, secret=False):
            tk.Label(body, text=label, bg='#06111a', fg='#86a8b8', anchor='w').pack(fill='x', pady=(7, 2))
            entry = tk.Entry(body, textvariable=variable, show='•' if secret else '', bg='#0a202e', fg='white', insertbackground='#53e7ff', relief='flat', font=('Segoe UI', 11))
            entry.pack(fill='x', ipady=9)
            return entry

        if creating:
            field('Your name (Friday will call you by this name)', display_var)
        username_entry = field('Login ID', username_var)
        field('Password (minimum 8 characters)', password_var, secret=True)
        if creating:
            field('Confirm password', confirm_var, secret=True)
        tk.Checkbutton(
            body, text='Keep me signed in for background wake', variable=remember_var,
            bg='#06111a', fg='#dff9ff', selectcolor='#0b2a3a',
            activebackground='#06111a', activeforeground='white',
        ).pack(anchor='w', pady=(12, 4))
        tk.Label(body, textvariable=status_var, bg='#06111a', fg='#ff5c73', wraplength=420).pack(fill='x', pady=4)

        def submit() -> None:
            try:
                if creating:
                    if password_var.get() != confirm_var.get():
                        raise ValueError('Passwords do not match.')
                    profile = store.create(
                        username_var.get(), display_var.get(), password_var.get(),
                        legacy_data_dir=legacy_data_dir,
                        remember=remember_var.get(),
                    )
                else:
                    profile = store.authenticate(
                        username_var.get(), password_var.get(), remember=remember_var.get()
                    )
            except Exception as exc:
                status_var.set(str(exc))
                return
            profile.activate()
            result['profile'] = profile
            root.destroy()

        tk.Button(
            body, text=('CREATE & CONTINUE' if creating else 'SIGN IN'), command=submit,
            bg='#0b2a3a', fg='#6affb8', activebackground='#12445b',
            activeforeground='white', relief='flat', padx=18, pady=10,
            font=('Segoe UI', 10, 'bold'),
        ).pack(fill='x', pady=(10, 8))

        def switch_mode() -> None:
            mode['create'] = not creating
            render()

        if store.has_accounts():
            tk.Button(
                body,
                text=('Use an existing account' if creating else 'Create another local account'),
                command=switch_mode,
                bg='#06111a', fg='#53e7ff', activebackground='#06111a',
                activeforeground='white', relief='flat', cursor='hand2',
            ).pack()
        tk.Label(
            body,
            text='Passwords stay on this PC as salted hashes. API keys remain separate and are never shown here.',
            bg='#06111a', fg='#86a8b8', wraplength=420, justify='left',
        ).pack(side='bottom', fill='x', pady=(12, 0))
        username_entry.focus_set()
        root.bind('<Return>', lambda _event: submit())

    render()
    root.mainloop()
    return result['profile']


def sign_out_and_restart() -> None:
    ProfileStore().sign_out()
    env = dict(os.environ)
    for key in ('JARVIS_ACTIVE_PROFILE_ID', 'JARVIS_ACTIVE_USERNAME', 'JARVIS_ACTIVE_DISPLAY_NAME', 'JARVIS_ACTIVE_DATA_DIR'):
        env.pop(key, None)
    if getattr(sys, 'frozen', False):
        command = [sys.executable]
        cwd = str(Path(sys.executable).resolve().parent)
    else:
        script = Path(__file__).resolve().parents[1] / 'desktop_app.py'
        command = [sys.executable, str(script)]
        cwd = str(script.parent)
    subprocess.Popen(command, cwd=cwd, env=env, shell=False)
