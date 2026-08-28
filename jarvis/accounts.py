from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .product_paths import PATHS


_ACCOUNTS_DB = PATHS.data_dir / 'accounts.db'
_ACTIVE_PROFILE = PATHS.data_dir / 'active_profile.json'
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,48}$")
_USERNAME_RE = re.compile(r'^[a-z0-9][a-z0-9_.-]{2,31}$')
_PBKDF2_ROUNDS = 310_000


@dataclass(frozen=True)
class UserProfile:
    id: int
    username: str
    display_name: str

    @property
    def profile_dir(self) -> Path:
        return PATHS.data_dir / 'profiles' / str(self.id)


class AccountStore:
    """Small local account store for per-user JARVIS profiles.

    Passwords are never stored directly. Each password is PBKDF2-HMAC-SHA256
    derived with a unique random salt. This is a local desktop identity boundary,
    not a cloud authentication service.
    """

    def __init__(self, db_path: Path = _ACCOUNTS_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Own and always close a SQLite connection, including on Windows errors.

        sqlite3.Connection's own context manager commits/rolls back but does not
        guarantee close. Explicit close prevents Windows file locks and keeps the
        account store safe for installer repair, backup and test cleanup.
        """
        db = self._connect()
        try:
            yield db
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            db.close()

    def _init_schema(self) -> None:
        with self._connection() as db:
            db.execute(
                '''CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TEXT
                )'''
            )
            db.commit()

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _PBKDF2_ROUNDS)

    @staticmethod
    def _validate(username: str, display_name: str, password: str) -> tuple[str, str]:
        user = username.strip().lower()
        name = ' '.join(display_name.strip().split())
        if not _USERNAME_RE.fullmatch(user):
            raise ValueError('Username 3-32 chars ka ho: letters, numbers, dot, dash ya underscore.')
        if not _NAME_RE.fullmatch(name):
            raise ValueError('Name 2-49 normal characters ka hona chahiye.')
        if len(password) < 6:
            raise ValueError('Password kam se kam 6 characters ka hona chahiye.')
        if len(password) > 200:
            raise ValueError('Password too long.')
        return user, name

    def create(self, username: str, display_name: str, password: str) -> UserProfile:
        user, name = self._validate(username, display_name, password)
        salt = secrets.token_bytes(16)
        digest = self._derive(password, salt)
        try:
            with self._connection() as db:
                cur = db.execute(
                    'INSERT INTO accounts(username, display_name, password_salt, password_hash) VALUES(?,?,?,?)',
                    (user, name, salt, digest),
                )
                db.commit()
                profile = UserProfile(int(cur.lastrowid), user, name)
        except sqlite3.IntegrityError as exc:
            raise ValueError('Ye username already use me hai.') from exc
        profile.profile_dir.mkdir(parents=True, exist_ok=True)
        return profile

    def authenticate(self, username: str, password: str) -> UserProfile | None:
        user = username.strip().lower()
        with self._connection() as db:
            row = db.execute('SELECT * FROM accounts WHERE username=?', (user,)).fetchone()
            if row is None:
                return None
            candidate = self._derive(password, bytes(row['password_salt']))
            if not hmac.compare_digest(candidate, bytes(row['password_hash'])):
                return None
            db.execute('UPDATE accounts SET last_login_at=CURRENT_TIMESTAMP WHERE id=?', (row['id'],))
            db.commit()
            return UserProfile(int(row['id']), str(row['username']), str(row['display_name']))

    def get(self, profile_id: int) -> UserProfile | None:
        with self._connection() as db:
            row = db.execute('SELECT id, username, display_name FROM accounts WHERE id=?', (int(profile_id),)).fetchone()
        if row is None:
            return None
        return UserProfile(int(row['id']), str(row['username']), str(row['display_name']))

    def count(self) -> int:
        with self._connection() as db:
            row = db.execute('SELECT COUNT(*) AS n FROM accounts').fetchone()
        return int(row['n'])


def remember_active_profile(profile: UserProfile) -> None:
    _ACTIVE_PROFILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _ACTIVE_PROFILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'profile_id': profile.id}), encoding='utf-8')
    tmp.replace(_ACTIVE_PROFILE)


def active_profile(store: AccountStore | None = None) -> UserProfile | None:
    store = store or AccountStore()
    try:
        payload = json.loads(_ACTIVE_PROFILE.read_text(encoding='utf-8'))
        return store.get(int(payload.get('profile_id')))
    except Exception:
        return None


def clear_active_profile() -> None:
    try:
        _ACTIVE_PROFILE.unlink(missing_ok=True)
    except Exception:
        pass


def activate_profile_environment(profile: UserProfile) -> None:
    """Select a per-user memory/audit/export namespace before importing Settings."""
    profile.profile_dir.mkdir(parents=True, exist_ok=True)
    exports = profile.profile_dir / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    os.environ['JARVIS_PROFILE_ID'] = str(profile.id)
    os.environ['USER_NAME'] = profile.display_name
    os.environ['JARVIS_DB_PATH'] = str(profile.profile_dir / 'jarvis.db')
    os.environ['JARVIS_EXPORT_DIR'] = str(exports)


def run_account_gate(*, background: bool = False) -> UserProfile | None:
    """Return the remembered profile or show a compact local Login/Create Account gate."""
    store = AccountStore()
    remembered = active_profile(store)
    if remembered is not None:
        activate_profile_environment(remembered)
        return remembered

    # Background startup must never show a mystery hidden process on a new device.
    # If there is no remembered identity, show the normal account gate once.
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title('JARVIS AI OMEGA // Account')
    root.geometry('440x430')
    root.resizable(False, False)
    root.configure(bg='#07131d')
    result: dict[str, UserProfile | None] = {'profile': None}

    title = tk.Label(root, text='JARVIS OMEGA', bg='#07131d', fg='#53e7ff', font=('Segoe UI', 21, 'bold'))
    title.pack(pady=(24, 3))
    tk.Label(root, text='LOGIN  •  CREATE ACCOUNT', bg='#07131d', fg='#86a8b8', font=('Consolas', 9, 'bold')).pack()

    form = tk.Frame(root, bg='#07131d')
    form.pack(fill='x', padx=42, pady=20)
    vars_ = {key: tk.StringVar() for key in ('name', 'username', 'password')}

    def field(label: str, key: str, secret: bool = False) -> None:
        tk.Label(form, text=label, bg='#07131d', fg='#dff9ff', anchor='w').pack(fill='x', pady=(6, 2))
        tk.Entry(form, textvariable=vars_[key], show='*' if secret else '', bg='#0a202e', fg='white', insertbackground='#53e7ff', relief='flat').pack(fill='x', ipady=7)

    field('Your name (Create Account)', 'name')
    field('Username', 'username')
    field('Password', 'password', True)

    buttons = tk.Frame(root, bg='#07131d')
    buttons.pack(fill='x', padx=42, pady=(4, 0))

    def finish(profile: UserProfile) -> None:
        remember_active_profile(profile)
        activate_profile_environment(profile)
        result['profile'] = profile
        root.destroy()

    def login() -> None:
        profile = store.authenticate(vars_['username'].get(), vars_['password'].get())
        if profile is None:
            messagebox.showerror('Login', 'Username ya password galat hai.', parent=root)
            return
        finish(profile)

    def signup() -> None:
        try:
            profile = store.create(vars_['username'].get(), vars_['name'].get(), vars_['password'].get())
        except Exception as exc:
            messagebox.showerror('Create Account', str(exc), parent=root)
            return
        finish(profile)

    tk.Button(buttons, text='LOGIN', command=login, bg='#0b2a3a', fg='#6affb8', relief='flat', pady=8).pack(fill='x', pady=3)
    tk.Button(buttons, text='CREATE ACCOUNT', command=signup, bg='#0b2a3a', fg='#53e7ff', relief='flat', pady=8).pack(fill='x', pady=3)
    tk.Label(root, text='Passwords stay local and are stored only as salted password hashes.', bg='#07131d', fg='#86a8b8', wraplength=360, justify='center', font=('Segoe UI', 8)).pack(pady=(13, 0))

    root.protocol('WM_DELETE_WINDOW', root.destroy)
    root.mainloop()
    return result['profile']


__all__ = [
    'AccountStore', 'UserProfile', 'activate_profile_environment', 'active_profile',
    'clear_active_profile', 'remember_active_profile', 'run_account_gate',
]
