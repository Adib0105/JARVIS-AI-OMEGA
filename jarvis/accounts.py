from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import tempfile
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
_MIN_SECRET_LENGTH = 6
_MAX_SECRET_LENGTH = 200
_MAX_AVATAR_BYTES = 16 * 1024 * 1024
_MAX_AVATAR_PIXELS = 40_000_000

@dataclass(frozen=True)
class UserProfile:
    id: int
    username: str
    display_name: str

    @property
    def profile_dir(self) -> Path:
        return PATHS.data_dir / 'profiles' / str(self.id)

    @property
    def avatar_path(self) -> Path:
        return self.profile_dir / 'avatar.png'

class AccountStore:
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
        db = self._connect()
        try:
            yield db
        except Exception:
            try:
                db.rollback()
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def _init_schema(self) -> None:
        with self._connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                recovery_salt BLOB,
                recovery_hash BLOB,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT
            )''')
            columns = {str(row['name']) for row in db.execute('PRAGMA table_info(accounts)').fetchall()}
            if 'recovery_salt' not in columns:
                db.execute('ALTER TABLE accounts ADD COLUMN recovery_salt BLOB')
            if 'recovery_hash' not in columns:
                db.execute('ALTER TABLE accounts ADD COLUMN recovery_hash BLOB')
            db.commit()

    @staticmethod
    def _derive(secret: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt, _PBKDF2_ROUNDS)

    @staticmethod
    def _validate_secret(secret: str, *, label: str) -> str:
        if not isinstance(secret, str):
            raise TypeError(f'{label} must be text.')
        if len(secret) < _MIN_SECRET_LENGTH or len(secret) > _MAX_SECRET_LENGTH:
            raise ValueError(f'{label} {_MIN_SECRET_LENGTH}-{_MAX_SECRET_LENGTH} characters ka hona chahiye.')
        return secret

    @classmethod
    def _validate_recovery_code(cls, code: str) -> str:
        if not isinstance(code, str):
            raise TypeError('Recovery code must be text.')
        normalized = code.strip()
        if normalized:
            cls._validate_secret(normalized, label='Recovery code')
        return normalized

    @staticmethod
    def _validate(username: str, display_name: str, password: str) -> tuple[str, str]:
        user = username.strip().lower(); name = ' '.join(display_name.strip().split())
        if not _USERNAME_RE.fullmatch(user): raise ValueError('Username 3-32 chars ka ho: letters, numbers, dot, dash ya underscore.')
        if not _NAME_RE.fullmatch(name): raise ValueError('Name 2-49 normal characters ka hona chahiye.')
        AccountStore._validate_secret(password, label='Password')
        return user, name

    def create(self, username: str, display_name: str, password: str, recovery_code: str = '') -> UserProfile:
        user, name = self._validate(username, display_name, password)
        salt = secrets.token_bytes(16); digest = self._derive(password, salt)
        recovery = self._validate_recovery_code(recovery_code)
        rsalt = secrets.token_bytes(16) if recovery else None
        rhash = self._derive(recovery, rsalt) if recovery and rsalt else None
        try:
            with self._connection() as db:
                cur = db.execute('INSERT INTO accounts(username,display_name,password_salt,password_hash,recovery_salt,recovery_hash) VALUES(?,?,?,?,?,?)', (user,name,salt,digest,rsalt,rhash))
                db.commit(); profile = UserProfile(int(cur.lastrowid), user, name)
        except sqlite3.IntegrityError as exc:
            raise ValueError('Ye username already use me hai.') from exc
        profile.profile_dir.mkdir(parents=True, exist_ok=True)
        return profile

    def authenticate(self, username: str, password: str) -> UserProfile | None:
        if not isinstance(password, str) or len(password) > _MAX_SECRET_LENGTH:
            return None
        user = username.strip().lower()
        with self._connection() as db:
            row = db.execute('SELECT * FROM accounts WHERE username=?', (user,)).fetchone()
            if row is None: return None
            if not hmac.compare_digest(self._derive(password, bytes(row['password_salt'])), bytes(row['password_hash'])): return None
            db.execute('UPDATE accounts SET last_login_at=CURRENT_TIMESTAMP WHERE id=?', (row['id'],)); db.commit()
            return UserProfile(int(row['id']), str(row['username']), str(row['display_name']))

    def get(self, profile_id: int) -> UserProfile | None:
        with self._connection() as db:
            row = db.execute('SELECT id,username,display_name FROM accounts WHERE id=?', (int(profile_id),)).fetchone()
        return None if row is None else UserProfile(int(row['id']), str(row['username']), str(row['display_name']))

    def count(self) -> int:
        with self._connection() as db: row = db.execute('SELECT COUNT(*) AS n FROM accounts').fetchone()
        return int(row['n'])

    def set_recovery_code(self, profile_id: int, code: str) -> None:
        code = self._validate_recovery_code(code)
        if not code:
            raise ValueError('Recovery code cannot be empty.')
        salt = secrets.token_bytes(16); digest = self._derive(code, salt)
        with self._connection() as db:
            cursor = db.execute(
                'UPDATE accounts SET recovery_salt=?, recovery_hash=? WHERE id=?',
                (salt, digest, int(profile_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError('Account not found.')
            db.commit()

    def reset_password(self, username: str, recovery_code: str, new_password: str) -> bool:
        self._validate_secret(new_password, label='New password')
        try:
            recovery = self._validate_recovery_code(recovery_code)
        except (TypeError, ValueError):
            return False
        if not recovery:
            return False
        with self._connection() as db:
            row = db.execute('SELECT * FROM accounts WHERE username=?', (username.strip().lower(),)).fetchone()
            if row is None or row['recovery_salt'] is None or row['recovery_hash'] is None: return False
            candidate = self._derive(recovery, bytes(row['recovery_salt']))
            if not hmac.compare_digest(candidate, bytes(row['recovery_hash'])): return False
            salt = secrets.token_bytes(16); digest = self._derive(new_password, salt)
            db.execute(
                '''UPDATE accounts
                   SET password_salt=?, password_hash=?, recovery_salt=NULL, recovery_hash=NULL
                   WHERE id=?''',
                (salt, digest, row['id']),
            )
            db.commit()
            return True

    def update_display_name(self, profile_id: int, display_name: str) -> UserProfile:
        name = ' '.join(display_name.strip().split())
        if not _NAME_RE.fullmatch(name): raise ValueError('Name 2-49 normal characters ka hona chahiye.')
        with self._connection() as db:
            db.execute('UPDATE accounts SET display_name=? WHERE id=?', (name,int(profile_id))); db.commit()
        profile = self.get(profile_id)
        if profile is None: raise ValueError('Account not found.')
        return profile

    def set_avatar(self, profile: UserProfile, source: Path) -> Path:
        from PIL import Image

        source = Path(source)
        if not source.is_file():
            raise ValueError('Profile photo file not found.')
        if source.stat().st_size > _MAX_AVATAR_BYTES:
            raise ValueError('Profile photo is too large.')
        profile.profile_dir.mkdir(parents=True, exist_ok=True)
        target = profile.avatar_path
        temporary: Path | None = None
        try:
            with Image.open(source) as image:
                if image.width * image.height > _MAX_AVATAR_PIXELS:
                    raise ValueError('Profile photo dimensions are too large.')
                image = image.convert('RGB')
                image.thumbnail((512, 512))
                side = min(image.size)
                left = (image.width - side) // 2
                top = (image.height - side) // 2
                avatar = image.crop((left, top, left + side, top + side)).resize((256, 256))
                with tempfile.NamedTemporaryFile(
                    mode='wb',
                    prefix='.avatar-',
                    suffix='.png',
                    dir=profile.profile_dir,
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    avatar.save(handle, 'PNG')
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target

def remember_active_profile(profile: UserProfile) -> None:
    _ACTIVE_PROFILE.parent.mkdir(parents=True, exist_ok=True); tmp = _ACTIVE_PROFILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'profile_id': profile.id}), encoding='utf-8'); tmp.replace(_ACTIVE_PROFILE)

def active_profile(store: AccountStore | None = None) -> UserProfile | None:
    store = store or AccountStore()
    try:
        payload = json.loads(_ACTIVE_PROFILE.read_text(encoding='utf-8')); return store.get(int(payload.get('profile_id')))
    except Exception: return None

def clear_active_profile() -> None:
    try: _ACTIVE_PROFILE.unlink(missing_ok=True)
    except Exception: pass

def activate_profile_environment(profile: UserProfile) -> None:
    profile.profile_dir.mkdir(parents=True, exist_ok=True); exports = profile.profile_dir/'exports'; exports.mkdir(parents=True, exist_ok=True)
    os.environ['JARVIS_PROFILE_ID']=str(profile.id); os.environ['USER_NAME']=profile.display_name
    os.environ['JARVIS_DB_PATH']=str(profile.profile_dir/'jarvis.db'); os.environ['JARVIS_EXPORT_DIR']=str(exports)

def run_account_gate(*, background: bool = False) -> UserProfile | None:
    store = AccountStore(); remembered = active_profile(store)
    if remembered is not None: activate_profile_environment(remembered); return remembered
    import tkinter as tk
    from tkinter import messagebox
    root=tk.Tk(); root.title('JARVIS AI OMEGA // Account'); root.geometry('460x560'); root.resizable(False,False); root.configure(bg='#07131d')
    result={'profile':None}
    tk.Label(root,text='JARVIS OMEGA',bg='#07131d',fg='#53e7ff',font=('Segoe UI',21,'bold')).pack(pady=(22,3))
    tk.Label(root,text='LOGIN  •  CREATE ACCOUNT',bg='#07131d',fg='#86a8b8',font=('Consolas',9,'bold')).pack()
    form=tk.Frame(root,bg='#07131d'); form.pack(fill='x',padx=42,pady=14)
    vars_={key:tk.StringVar() for key in ('name','username','password','recovery')}
    def field(label,key,secret=False):
        tk.Label(form,text=label,bg='#07131d',fg='#dff9ff',anchor='w').pack(fill='x',pady=(5,2)); tk.Entry(form,textvariable=vars_[key],show='*' if secret else '',bg='#0a202e',fg='white',insertbackground='#53e7ff',relief='flat').pack(fill='x',ipady=7)
    field('Your name (Create Account)','name'); field('Username','username'); field('Password','password',True); field('One-time recovery code (Create Account)','recovery',True)
    buttons=tk.Frame(root,bg='#07131d'); buttons.pack(fill='x',padx=42,pady=(2,0))
    def finish(profile): remember_active_profile(profile); activate_profile_environment(profile); result['profile']=profile; root.destroy()
    def login():
        p=store.authenticate(vars_['username'].get(),vars_['password'].get())
        if p is None: messagebox.showerror('Login','Username ya password galat hai.',parent=root)
        else: finish(p)
    def signup():
        try: finish(store.create(vars_['username'].get(),vars_['name'].get(),vars_['password'].get(),vars_['recovery'].get()))
        except Exception as exc: messagebox.showerror('Create Account',str(exc),parent=root)
    def forgot():
        user=vars_['username'].get().strip()
        if not user: messagebox.showinfo('Forgot Password','Pehle username enter karo.',parent=root); return
        win=tk.Toplevel(root); win.title('Reset Password'); win.geometry('390x260'); win.configure(bg='#07131d'); win.transient(root); win.grab_set()
        rc=tk.StringVar(); np=tk.StringVar()
        for label,var in [('Recovery PIN/code',rc),('New password',np)]:
            tk.Label(win,text=label,bg='#07131d',fg='#dff9ff').pack(anchor='w',padx=30,pady=(18,3)); tk.Entry(win,textvariable=var,show='*',bg='#0a202e',fg='white',insertbackground='#53e7ff',relief='flat').pack(fill='x',padx=30,ipady=7)
        def reset():
            try: ok=store.reset_password(user,rc.get(),np.get())
            except Exception as exc: messagebox.showerror('Reset Password',str(exc),parent=win); return
            if not ok: messagebox.showerror('Reset Password','Recovery code galat hai, already use ho chuka hai, ya is purane account me recovery setup nahi hai.',parent=win); return
            messagebox.showinfo('Reset Password','Password reset ho gaya. Ye recovery code ab use ho chuka hai; LOGIN ke baad naya code set karna.',parent=win); win.destroy()
        tk.Button(win,text='RESET PASSWORD',command=reset,bg='#0b2a3a',fg='#53e7ff',relief='flat',pady=8).pack(fill='x',padx=30,pady=18)
    tk.Button(buttons,text='LOGIN',command=login,bg='#0b2a3a',fg='#6affb8',relief='flat',pady=8).pack(fill='x',pady=3)
    tk.Button(buttons,text='CREATE ACCOUNT',command=signup,bg='#0b2a3a',fg='#53e7ff',relief='flat',pady=8).pack(fill='x',pady=3)
    tk.Button(buttons,text='FORGOT PASSWORD',command=forgot,bg='#0b2a3a',fg='#ffd166',relief='flat',pady=7).pack(fill='x',pady=3)
    tk.Label(root,text='Password aur one-time recovery code local salted hashes me store hote hain.',bg='#07131d',fg='#86a8b8',wraplength=370,font=('Segoe UI',8)).pack(pady=(10,0))
    root.protocol('WM_DELETE_WINDOW',root.destroy); root.mainloop(); return result['profile']

__all__=['AccountStore','UserProfile','activate_profile_environment','active_profile','clear_active_profile','remember_active_profile','run_account_gate']
