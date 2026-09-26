"""Transactional accounts, opaque sessions and server-owned entitlements."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

ROUNDS = 600_000
SESSION_TTL = 7 * 86400


def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ROUNDS)


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    salt BLOB NOT NULL, password BLOB NOT NULL,
                    failures INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0,
                    customer TEXT UNIQUE, checkout_id TEXT, checkout_tier TEXT, checkout_generation INTEGER NOT NULL DEFAULT 0,
                    created INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    status TEXT NOT NULL, period_end INTEGER NOT NULL, price TEXT NOT NULL,
                    cancel_at_period_end INTEGER NOT NULL, checked INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, received INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS rates (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
            ''')
        try:
            Path(path).chmod(0o600)
        except OSError:
            pass

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def rate(self, key, limit, seconds):
        now = int(time.time())
        key = hashlib.sha256(key.encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rates WHERE expires<=?', (now,))
            db.execute('INSERT INTO rates VALUES (?,0,?) ON CONFLICT(key) DO NOTHING', (key, now + seconds))
            db.execute('UPDATE rates SET count=count+1 WHERE key=?', (key,))
            return db.execute('SELECT count FROM rates WHERE key=?', (key,)).fetchone()[0] <= limit

    def register(self, email, name, password):
        salt = secrets.token_bytes(16)
        hashed = digest(password, salt)
        with self.db() as db:
            uid = uuid.uuid4().hex
            try:
                db.execute('INSERT INTO users(id,email,name,salt,password,created) VALUES(?,?,?,?,?,?)',
                           (uid, email, name, salt, hashed, int(time.time())))
            except sqlite3.IntegrityError as exc:
                raise ValueError('Account cannot be created. Try signing in.') from exc
        return self.login(email, password)

    def login(self, email, password):
        now = int(time.time())
        token = secrets.token_urlsafe(32)
        error = None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            actual = digest(password, row['salt'] if row else b'\0' * 16)
            if not row or row['locked_until'] > now or not hmac.compare_digest(actual, row['password']):
                if row and row['locked_until'] <= now:
                    failures = row['failures'] + 1
                    db.execute('UPDATE users SET failures=?,locked_until=? WHERE id=?',
                               (0 if failures >= 5 else failures, now + 60 if failures >= 5 else 0, row['id']))
                error = PermissionError('Login failed. Check credentials or wait before retrying.')
            else:
                db.execute('UPDATE users SET failures=0,locked_until=0 WHERE id=?', (row['id'],))
                db.execute('DELETE FROM sessions WHERE expires<=?', (now,))
                db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], now + SESSION_TTL))
                # Bound remembered devices without retaining old tokens forever.
                db.execute('DELETE FROM sessions WHERE user_id=? AND digest NOT IN (SELECT digest FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT 10)', (row['id'], row['id']))
        if error:
            raise error
        return {'access_token': token, 'expires_at': now + SESSION_TTL, 'token_type': 'bearer'}

    def user(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise PermissionError('Sign in required.')
        with self.db() as db:
            row = db.execute('SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.digest=? AND s.expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if row is None:
            raise PermissionError('Session expired. Sign in again.')
        return dict(row)

    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE digest=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self, uid, old, new):
        error = None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            now = int(time.time())
            if row['locked_until'] > now or not hmac.compare_digest(digest(old, row['salt']), row['password']):
                failures = row['failures'] + 1
                db.execute('UPDATE users SET failures=?,locked_until=? WHERE id=?', (failures, now + 60 if failures >= 5 else 0, uid))
                error = PermissionError('Password change failed. Check credentials or wait.')
            else:
                salt = secrets.token_bytes(16)
                db.execute('UPDATE users SET salt=?,password=?,failures=0,locked_until=0 WHERE id=?', (salt, digest(new, salt), uid))
                db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        if error:
            raise error

    def entitlement(self, uid, allowed_prices):
        now = int(time.time())
        with self.db() as db:
            rows = db.execute('SELECT * FROM subscriptions WHERE user_id=? ORDER BY period_end DESC', (uid,)).fetchall()
        active = next((r for r in rows if r['status'] in ('active', 'trialing') and r['period_end'] > now and r['price'] in allowed_prices and now - r['checked'] <= 86400), None)
        latest = active or (rows[0] if rows else None)
        return {'plan': 'pro' if active else 'free', 'features': ['extended_forecast'] if active else [],
                'status': latest['status'] if latest else 'none', 'expires_at': latest['period_end'] if latest else None,
                'cancel_at_period_end': bool(latest['cancel_at_period_end']) if latest else False}
