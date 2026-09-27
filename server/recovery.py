"""Single-use email ownership/reset tokens; raw tokens never enter the database."""
from __future__ import annotations

import hashlib
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

from .store import digest

GENERIC = {'ok': True, 'message': 'If the account exists and mail is configured, a code has been sent.'}


class Mailer:
    def __init__(self, config):
        self.config = config

    @property
    def configured(self):
        return all(self.config.get(k) for k in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_FROM'))

    def send(self, recipient, kind, token):
        if not self.configured:
            raise RuntimeError('Account email delivery is not configured.')
        message = EmailMessage()
        message['From'] = self.config['SMTP_FROM']
        message['To'] = recipient
        message['Subject'] = 'JARVIS ' + ('email verification' if kind == 'verify' else 'password reset')
        message.set_content('Enter this single-use code in JARVIS Account / Subscription. It expires in 15 minutes.\n\n'
                            + token + '\n\nIf you did not request this, ignore this email. Never share the code.')
        # TLS is mandatory, certificate verification remains enabled.
        with smtplib.SMTP_SSL(self.config['SMTP_HOST'], int(self.config.get('SMTP_PORT', '465')),
                              timeout=10, context=ssl.create_default_context()) as smtp:
            smtp.login(self.config['SMTP_USER'], self.config['SMTP_PASSWORD'])
            smtp.send_message(message)


class Recovery:
    def __init__(self, store, mailer):
        self.store, self.mailer = store, mailer

    def request(self, email, kind):
        if kind not in ('verify', 'reset'):
            raise ValueError('Invalid account operation.')
        if not self.store.rate('recovery:' + email, 3, 3600):
            return GENERIC
        with self.store.db() as db:
            user = db.execute('SELECT id,email,email_verified FROM users WHERE email=?', (email,)).fetchone()
        if not user or not self.mailer.configured or (kind == 'verify' and user['email_verified']):
            return GENERIC
        token = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(token.encode()).hexdigest()
        with self.store.db() as db:
            db.execute('DELETE FROM account_tokens WHERE expires<=? OR (user_id=? AND kind=?)', (int(time.time()), user['id'], kind))
            db.execute('INSERT INTO account_tokens VALUES(?,?,?,?,?)', (hashed, user['id'], kind, int(time.time()) + 900, 0))
        try:
            self.mailer.send(user['email'], kind, token)
        except (OSError, RuntimeError, smtplib.SMTPException):
            # Delivery failure cannot leave a usable undisclosed reset code.
            with self.store.db() as db:
                db.execute('DELETE FROM account_tokens WHERE digest=?', (hashed,))
        return GENERIC

    def consume(self, token, kind, new_password=None):
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise ValueError('Code is invalid or expired.')
        hashed = hashlib.sha256(token.encode()).hexdigest()
        salt = secrets.token_bytes(16)
        # Expensive work is outside the short atomic consume/update transaction.
        new_hash = digest(new_password, salt) if kind == 'reset' else None
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM account_tokens WHERE digest=? AND kind=? AND used=0 AND expires>?',
                             (hashed, kind, int(time.time()))).fetchone()
            if row is None:
                raise ValueError('Code is invalid or expired.')
            if kind == 'reset':
                db.execute('UPDATE users SET salt=?,password=?,email_verified=1,failures=0,locked_until=0 WHERE id=?', (salt, new_hash, row['user_id']))
                db.execute('DELETE FROM sessions WHERE user_id=?', (row['user_id'],))
                db.execute('DELETE FROM account_tokens WHERE user_id=?', (row['user_id'],))
            else:
                db.execute('UPDATE users SET email_verified=1 WHERE id=?', (row['user_id'],))
                db.execute('UPDATE account_tokens SET used=1 WHERE digest=?', (hashed,))
        return {'ok': True, 'sign_in_required': kind == 'reset'}
