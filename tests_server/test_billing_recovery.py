import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from server.billing import Billing
from server.store import Store


class DurableStripe:
    def __init__(self):
        self.saved = {}
        self.fail_after_create = False
        self.posts = []
        self.subscriptions = {}

    def call(self, method, path, data=None, idempotency=None):
        if path == 'customers':
            return {'id': 'cus_' + data['metadata[user_id]']}
        if path == 'checkout/sessions':
            self.posts.append(idempotency)
            self.saved.setdefault(idempotency, {'id': 'cs_1', 'status': 'open', 'url': 'https://checkout.stripe.com/c/pay/test'})
            if self.fail_after_create:
                self.fail_after_create = False
                raise RuntimeError('Connection lost after provider success')
            return self.saved[idempotency]
        if path.startswith('checkout/sessions/'):
            return next(iter(self.saved.values()))
        return self.subscriptions[path.rsplit('/', 1)[1]]


class BillingRecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / 'accounts.db')
        self.gateway = DurableStripe()
        self.billing = Billing(self.store, self.gateway, {'monthly': 'price_month'}, 'https://accounts.example.com')
        with patch('server.store.ROUNDS', 1000):
            session = self.store.register('test@example.com', 'Adib', 'password-for-tests')
        self.user = self.store.user(session['access_token'])
        with self.store.db() as db:
            db.execute('UPDATE users SET email_verified=1 WHERE id=?', (self.user['id'],))

    def test_slow_checkout_does_not_lock_unrelated_requests(self):
        entered, release = threading.Event(), threading.Event()
        original = self.gateway.call
        def slow(*args, **kwargs):
            entered.set()
            release.wait(2)
            return original(*args, **kwargs)
        errors = []
        def checkout():
            try:
                self.billing.checkout(self.user, 'monthly')
            except Exception as exc:
                errors.append(exc)
        with patch.object(self.gateway, 'call', side_effect=slow):
            thread = threading.Thread(target=checkout)
            thread.start()
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertTrue(self.store.rate('unrelated', 5, 60))
            self.assertLess(time.monotonic() - start, .5)
            with self.assertRaisesRegex(RuntimeError, 'in progress'):
                self.billing.checkout(self.user, 'monthly')
            release.set()
            thread.join(2)
        self.assertFalse(errors)
        self.assertEqual(len(set(self.gateway.posts)), 1)

    def test_uncertain_provider_success_reuses_durable_intent(self):
        self.gateway.fail_after_create = True
        with self.assertRaises(RuntimeError):
            self.billing.checkout(self.user, 'monthly')
        restarted = Billing(self.store, self.gateway, self.billing.prices, self.billing.public_url)
        self.assertTrue(restarted.checkout(self.user, 'monthly').startswith('https://checkout.stripe.com/'))
        self.assertEqual(len(self.gateway.saved), 1)
        self.assertEqual(self.gateway.posts[0], self.gateway.posts[1])

    def test_old_uncertain_intent_cannot_replay_expired_idempotency_key(self):
        self.gateway.fail_after_create = True
        with self.assertRaises(RuntimeError):
            self.billing.checkout(self.user, 'monthly')
        with self.store.db() as db:
            db.execute('UPDATE checkout_intents SET created=0')
        with self.assertRaisesRegex(RuntimeError, 'reconciliation'):
            self.billing.checkout(self.user, 'monthly')
        self.assertEqual(len(self.gateway.posts), 1)

    def test_failed_webhook_is_durable_and_recovers_after_restart(self):
        self.billing.checkout(self.user, 'monthly')
        user = self.billing._user(self.user['id'])
        event = {'id': 'evt_retry', 'type': 'customer.subscription.updated', 'data': {'object': {'id': 'sub_retry', 'customer': user['customer']}}}
        with patch.object(self.gateway, 'call', side_effect=RuntimeError('provider unavailable')):
            with self.assertRaises(RuntimeError):
                self.billing.webhook(event)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM billing_inbox').fetchone()
            self.assertEqual(row['processed'], 0)
            self.assertEqual(row['attempts'], 1)
            db.execute('UPDATE billing_inbox SET retry_at=0')
        self.gateway.subscriptions['sub_retry'] = {'id': 'sub_retry', 'customer': user['customer'], 'status': 'active', 'items': {'data': [{'price': {'id': 'price_month'}, 'current_period_end': int(time.time()) + 3600}]}}
        self.billing.retry_pending()
        self.assertEqual(self.store.entitlement(user['id'], self.billing.prices.values())['plan'], 'pro')
        self.billing.webhook(event)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 1)

    def test_password_hashing_is_outside_write_transaction(self):
        import server.store as module
        original = module.digest
        def hashing(*args):
            # A separate writer must work while the hash function is active.
            self.assertTrue(self.store.rate('during-hash', 10, 60))
            return original(*args)
        with patch('server.store.ROUNDS', 1000), patch('server.store.digest', side_effect=hashing):
            self.store.login('test@example.com', 'password-for-tests')
            self.store.change_password(self.user['id'], 'password-for-tests', 'different-password')

class AccountRecoveryTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from server.app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sent = []
        mailer = type('FakeMailer', (), {'configured': True, 'send': lambda _, email, kind, code: self.sent.append((email, kind, code))})()
        self.app = create_app(db_path=Path(self.tmp.name) / 'auth.db', gateway=DurableStripe(), mailer=mailer,
                              config={'JARVIS_PUBLIC_URL': 'https://accounts.example.com', 'STRIPE_PRICE_MONTHLY': 'price_month'})
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        result = self.client.post('/auth/register', json={'email': 'owner@example.com', 'name': 'Adib', 'password': 'initial-long-password'})
        self.headers = {'Authorization': 'Bearer ' + result.json()['access_token']}

    def request_code(self, kind, email='owner@example.com'):
        return self.client.post('/auth/request-code', json={'email': email, 'kind': kind})

    def test_unverified_email_cannot_start_paid_checkout(self):
        response = self.client.post('/billing/checkout', json={'plan': 'monthly'}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.request_code('verify')
        code = self.sent[-1][2]
        self.assertEqual(self.client.post('/auth/verify-email', json={'code': code}).status_code, 200)
        self.assertEqual(self.client.post('/auth/verify-email', json={'code': code}).status_code, 400)
        self.assertTrue(self.client.get('/me', headers=self.headers).json()['email_verified'])
        self.assertEqual(self.client.post('/billing/checkout', json={'plan': 'monthly'}, headers=self.headers).status_code, 200)

    def test_reset_revokes_sessions_and_raw_code_is_not_stored(self):
        self.request_code('reset')
        code = self.sent[-1][2]
        with self.app.state.store.db() as db:
            self.assertNotIn(code, str([tuple(row) for row in db.execute('SELECT * FROM account_tokens')]))
        result = self.client.post('/auth/reset-password', json={'code': code, 'new_password': 'replacement-long-password'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get('/me', headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/auth/reset-password', json={'code': code, 'new_password': 'another-long-password'}).status_code, 400)
        self.assertEqual(self.client.post('/auth/login', json={'email': 'owner@example.com', 'password': 'replacement-long-password'}).status_code, 200)

    def test_unknown_email_and_expired_code_do_not_leak_or_reset(self):
        a = self.request_code('reset').json()
        b = self.request_code('reset', 'missing@example.com').json()
        self.assertEqual(a, b)
        self.assertEqual(len(self.sent), 1)
        with self.app.state.store.db() as db:
            db.execute('UPDATE account_tokens SET expires=0')
        self.assertEqual(self.client.post('/auth/reset-password', json={'code': self.sent[0][2], 'new_password': 'replacement-long-password'}).status_code, 400)


class BackupTests(unittest.TestCase):
    def test_snapshot_copies_committed_wal_state_and_never_overwrites(self):
        import sqlite3
        from server.backup import backup
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'live.db', Path(folder) / 'backup.db'
            connection = sqlite3.connect(source)
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('CREATE TABLE sample(value TEXT)')
                connection.execute('INSERT INTO sample VALUES (?)', ('committed',))
                connection.commit()
                backup(source, target)
                copied = sqlite3.connect(target)
                try:
                    self.assertEqual(copied.execute('SELECT value FROM sample').fetchone()[0], 'committed')
                    self.assertEqual(copied.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                finally:
                    copied.close()
                before = target.read_bytes()
                with self.assertRaises(ValueError):
                    backup(source, target)
                self.assertEqual(target.read_bytes(), before)
            finally:
                connection.close()
