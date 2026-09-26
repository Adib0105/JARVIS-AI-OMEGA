"""HTTP, authentication and billing regressions with a fake payment provider."""
import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from server.app import create_app
from server.billing import verify_event


class FakeStripe:
    def __init__(self):
        self.calls = []
        self.subscriptions = {}
        self.sessions = {}

    def call(self, method, path, data=None, idempotency=None):
        self.calls.append((method, path, data, idempotency))
        if path == 'customers':
            return {'id': 'cus_' + data['metadata[user_id]']}
        if path == 'checkout/sessions':
            sid = 'cs_' + str(len(self.sessions) + 1)
            self.sessions[sid] = {'id': sid, 'status': 'open', 'url': 'https://checkout.stripe.com/c/pay/' + sid}
            return self.sessions[sid]
        if path.startswith('checkout/sessions/'):
            return self.sessions[path.rsplit('/', 1)[1]]
        if path == 'billing_portal/sessions':
            return {'url': 'https://billing.stripe.com/p/session/test'}
        if path.startswith('subscriptions/'):
            return self.subscriptions[path.rsplit('/', 1)[1]]
        raise AssertionError('Unexpected Stripe request: ' + path)


class BillingHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gateway = FakeStripe()
        self.config = {'JARVIS_PUBLIC_URL': 'https://accounts.example.com', 'STRIPE_SECRET_KEY': 'test-only',
                       'STRIPE_WEBHOOK_SECRET': 'test-webhook-secret', 'STRIPE_PRICE_MONTHLY': 'price_month',
                       'STRIPE_PRICE_YEARLY': 'price_year', 'OPEN_METEO_API_KEY': 'test-weather'}
        self.app = create_app(db_path=Path(self.tmp.name) / 'test.sqlite3', gateway=self.gateway, config=self.config)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.auth = self.register('adib@example.com')

    def register(self, email):
        r = self.client.post('/auth/register', json={'email': email, 'name': 'Adib', 'password': 'long-test-password'})
        self.assertEqual(r.status_code, 200, r.text)
        return {'Authorization': 'Bearer ' + r.json()['access_token']}

    def checkout(self, auth=None, plan='monthly'):
        return self.client.post('/billing/checkout', json={'plan': plan}, headers=auth or self.auth)

    def send_event(self, sid='sub_123', eid='evt_123', stamp=None, secret=None, kind='customer.subscription.updated'):
        raw = json.dumps({'id': eid, 'type': kind, 'data': {'object': {'id': sid}}}).encode()
        stamp = int(time.time()) if stamp is None else stamp
        signature = hmac.new((secret or self.config['STRIPE_WEBHOOK_SECRET']).encode(), str(stamp).encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return self.client.post('/billing/webhook', content=raw, headers={'Stripe-Signature': f't={stamp},v1={signature}'})

    def activate(self, auth=None, sid='sub_123', eid='evt_123'):
        auth = auth or self.auth
        self.assertEqual(self.checkout(auth).status_code, 200)
        who = self.app.state.store.user(auth['Authorization'][7:])
        self.gateway.subscriptions[sid] = {'id': sid, 'customer': who['customer'], 'status': 'active', 'cancel_at_period_end': False,
            'items': {'data': [{'price': {'id': 'price_month'}, 'current_period_end': int(time.time()) + 86400}]}}
        self.assertEqual(self.send_event(sid=sid, eid=eid).status_code, 200)

    def me(self, auth=None):
        return self.client.get('/me', headers=auth or self.auth).json()

    def test_account_login_logout_and_password_hashes(self):
        self.assertEqual(self.me()['name'], 'Adib')
        with self.app.state.store.db() as db:
            row = db.execute('SELECT * FROM users').fetchone()
            self.assertNotIn(b'long-test-password', row['password'])
            token = self.auth['Authorization'][7:]
            self.assertNotEqual(db.execute('SELECT digest FROM sessions').fetchone()[0], token)
        self.assertEqual(self.client.get('/me').status_code, 401)
        self.client.post('/auth/logout', headers=self.auth)
        self.assertEqual(self.client.get('/me', headers=self.auth).status_code, 401)
        login = self.client.post('/auth/login', json={'email': 'ADIB@example.com', 'password': 'long-test-password'})
        self.assertEqual(login.status_code, 200)

    def test_password_rotation_revokes_all_devices(self):
        second = self.client.post('/auth/login', json={'email': 'adib@example.com', 'password': 'long-test-password'}).json()['access_token']
        result = self.client.post('/auth/password', headers=self.auth, json={'current_password': 'long-test-password', 'new_password': 'new-strong-password'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get('/me', headers={'Authorization': 'Bearer ' + second}).status_code, 401)
        self.assertEqual(self.client.get('/me', headers=self.auth).status_code, 401)

    def test_wrong_password_lockout_is_persisted(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/auth/login', json={'email': 'adib@example.com', 'password': 'wrong-password'}).status_code, 401)
        self.assertEqual(self.client.post('/auth/login', json={'email': 'adib@example.com', 'password': 'long-test-password'}).status_code, 401)

    def test_no_client_plan_self_grant_or_cross_account_access(self):
        other = self.register('soni@example.com')
        self.activate()
        self.assertEqual(self.me()['subscription']['plan'], 'pro')
        self.assertEqual(self.me(other)['subscription']['plan'], 'free')
        self.assertEqual(self.client.post('/pro/forecast', headers=other, json={'plan': 'pro'}).status_code, 403)
        self.assertEqual(self.checkout(other, 'price_attacker').status_code, 400)

    def test_checkout_retries_reuse_session_and_prices_are_server_owned(self):
        a = self.checkout()
        b = self.checkout()
        self.assertEqual(a.json(), b.json())
        creates = [c for c in self.gateway.calls if c[0] == 'POST' and c[1] == 'checkout/sessions']
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0][2]['line_items[0][price]'], 'price_month')
        self.assertEqual(self.checkout(plan='yearly').status_code, 400)

    def test_redirect_page_never_grants_pro(self):
        self.checkout()
        self.assertEqual(self.client.get('/billing/success').status_code, 200)
        self.assertEqual(self.me()['subscription']['plan'], 'free')

    def test_webhook_signature_and_expiry_rejected(self):
        for kw in ({'secret': 'wrong-secret'}, {'stamp': int(time.time()) - 301}, {'stamp': int(time.time()) + 301}):
            self.assertEqual(self.send_event(**kw).status_code, 400)
        self.assertEqual(self.me()['subscription']['plan'], 'free')

    def test_duplicate_webhook_is_idempotent(self):
        self.activate()
        count = len(self.gateway.calls)
        self.assertEqual(self.send_event().status_code, 200)
        self.assertEqual(len(self.gateway.calls), count)
        with self.app.state.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 1)

    def test_out_of_order_event_fetches_current_cancellation(self):
        self.activate()
        self.gateway.subscriptions['sub_123']['status'] = 'canceled'
        self.send_event(eid='evt_late_old_active')
        self.assertEqual(self.me()['subscription']['plan'], 'free')

    def test_subscription_expiry_unknown_price_and_delinquency_fail_closed(self):
        self.activate()
        sub = self.gateway.subscriptions['sub_123']
        for idx, status in enumerate(('past_due', 'unpaid', 'incomplete', 'paused', 'canceled')):
            sub['status'] = status
            self.send_event(eid='evt_state_' + str(idx))
            self.assertEqual(self.me()['subscription']['plan'], 'free')
        sub['status'] = 'active'
        sub['items']['data'][0]['price']['id'] = 'price_other_product'
        self.send_event(eid='evt_unknown_price')
        self.assertEqual(self.me()['subscription']['plan'], 'free')
        sub['items']['data'][0]['price']['id'] = 'price_month'
        sub['items']['data'][0]['current_period_end'] = int(time.time()) - 1
        self.send_event(eid='evt_expired')
        self.assertEqual(self.me()['subscription']['plan'], 'free')

    def test_cancel_at_end_keeps_paid_time_and_blocks_second_checkout(self):
        self.activate()
        sub = self.gateway.subscriptions['sub_123']
        sub['cancel_at_period_end'] = True
        self.send_event(eid='evt_cancel_later')
        self.assertEqual(self.me()['subscription']['plan'], 'pro')
        self.assertTrue(self.me()['subscription']['cancel_at_period_end'])
        self.assertEqual(self.checkout().status_code, 400)
        self.assertIn('billing.stripe.com', self.client.post('/billing/portal', headers=self.auth).json()['url'])

    def test_pro_forecast_is_authorized_on_server_each_time(self):
        self.activate()
        with patch('jarvis.daily_briefing.weather_report', return_value='7 days of actual data') as weather:
            result = self.client.post('/pro/forecast', headers=self.auth, json={'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(weather.call_args.kwargs['mode'], 'week')
        self.gateway.subscriptions['sub_123']['status'] = 'canceled'
        self.assertEqual(self.client.post('/pro/forecast', headers=self.auth, json={}).status_code, 403)

    def test_refresh_recovers_a_completed_checkout_when_webhook_is_delayed(self):
        self.checkout()
        who = self.app.state.store.user(self.auth['Authorization'][7:])
        self.gateway.sessions[who['checkout_id']].update(status='complete', subscription='sub_delayed')
        self.gateway.subscriptions['sub_delayed'] = {'id': 'sub_delayed', 'customer': who['customer'], 'status': 'active',
            'items': {'data': [{'price': {'id': 'price_month'}, 'current_period_end': int(time.time()) + 86400}]}}
        result = self.client.post('/billing/refresh', headers=self.auth)
        self.assertEqual(result.json()['plan'], 'pro')

    def test_free_commercial_weather_route_cannot_be_used_for_pro(self):
        location = {'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1}
        self.assertEqual(self.client.post('/weather/report', json=location).status_code, 401)
        with patch('jarvis.daily_briefing.rich_weather_report', return_value='grounded weather'):
            result = self.client.post('/weather/report', headers=self.auth, json=location)
        self.assertEqual(result.json()['report'], 'grounded weather')
        self.assertEqual(self.client.post('/weather/report', headers=self.auth, json=location | {'mode': 'week'}).status_code, 400)

    def test_bad_origins_request_limits_and_no_password_echo(self):
        self.assertEqual(self.client.get('/me', headers=self.auth | {'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.post('/auth/login', content='x' * 65537).status_code, 400)
        result = self.client.post('/auth/login', content='{"password":"super-secret"')
        self.assertEqual(result.status_code, 400)
        self.assertNotIn('super-secret', result.text)
        self.assertEqual(self.client.get('/health').headers['cache-control'], 'no-store')

    def test_billing_unconfigured_is_a_visible_error_not_fake_success(self):
        self.app.state.billing.prices.clear()
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(self.me()['subscription']['plan'], 'free')

    def test_login_http_rate_limit(self):
        # Avoid expensive PBKDF2 for this IP-rate behavior test.
        with patch.object(self.app.state.store, 'login', side_effect=PermissionError('Login failed.')):
            statuses = [self.client.post('/auth/login', json={'email': 'none@example.com', 'password': 'wrong'}).status_code for _ in range(21)]
        self.assertEqual(statuses[-1], 429)

    def test_stale_entitlement_needs_online_reconciliation(self):
        self.activate()
        with self.app.state.store.db() as db:
            db.execute('UPDATE subscriptions SET checked=?', (int(time.time()) - 86401,))
        self.assertEqual(self.me()['subscription']['plan'], 'free')
        self.assertEqual(self.client.post('/billing/refresh', headers=self.auth).json()['plan'], 'pro')


class WebhookParserTests(unittest.TestCase):
    def test_raw_body_tampering_fails(self):
        raw = b'{"id":"evt_good"}'
        stamp = str(int(time.time()))
        sig = hmac.new(b'secret', stamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        self.assertEqual(verify_event(raw, f't={stamp},v1={sig}', 'secret')['id'], 'evt_good')
        with self.assertRaises(ValueError):
            verify_event(raw + b' ', f't={stamp},v1={sig}', 'secret')

    def test_server_requires_https_except_local_development(self):
        for value in ('http://example.com', 'https://user:secret@example.com', 'https://example.com/path'):
            with self.assertRaises(ValueError):
                create_app(config={'JARVIS_PUBLIC_URL': value})
