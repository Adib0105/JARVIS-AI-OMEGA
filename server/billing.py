"""Fixed Stripe API origins, hosted payments and signed webhook reconciliation."""
from __future__ import annotations

import hashlib
import contextlib
import sqlite3
import uuid
import hmac
import json
import re
import time
from urllib.parse import urlsplit

import httpx


class StripeGateway:
    def __init__(self, secret):
        self.secret = secret

    def call(self, method, path, data=None, idempotency=None):
        if not self.secret:
            raise RuntimeError('Billing is not configured on this server.')
        headers = {'Authorization': 'Bearer ' + self.secret, 'Stripe-Version': '2025-03-31.basil'}
        if idempotency:
            headers['Idempotency-Key'] = idempotency
        try:
            with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
                response = client.request(method, 'https://api.stripe.com/v1/' + path, data=data, headers=headers)
                if response.status_code >= 300:
                    raise RuntimeError('Payment provider request failed. Try again later.')
                return response.json()
        except httpx.HTTPError:
            raise RuntimeError('Payment provider is unavailable.') from None


def hosted_url(value, host):
    parts = urlsplit(str(value))
    if parts.scheme != 'https' or parts.hostname != host or parts.username or parts.password or parts.port not in (None, 443):
        raise RuntimeError('Payment provider returned an unexpected URL.')
    return value


def verify_event(raw, signature, secret, now=None):
    if not secret:
        raise RuntimeError('Webhook signing secret is not configured.')
    if len(raw) > 65536 or len(signature) > 4096:
        raise ValueError('Invalid webhook.')
    values = [x.split('=', 1) for x in signature.split(',') if '=' in x]
    stamps = [v for k, v in values if k == 't']
    signatures = [v for k, v in values if k == 'v1']
    if len(stamps) != 1 or not stamps[0].isdigit() or abs((now or time.time()) - int(stamps[0])) > 300:
        raise ValueError('Invalid webhook timestamp.')
    expected = hmac.new(secret.encode(), stamps[0].encode() + b'.' + raw, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise ValueError('Invalid webhook signature.')
    event = json.loads(raw)
    if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not event['id'].startswith('evt_'):
        raise ValueError('Invalid webhook event.')
    return event


class Billing:
    """Short durable reservations; no provider I/O while holding a SQLite writer."""
    def __init__(self, store, gateway, prices, public_url):
        self.store, self.gateway, self.prices, self.public_url = store, gateway, prices, public_url

    @contextlib.contextmanager
    def _lease(self, uid):
        owner = uuid.uuid4().hex
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM billing_leases WHERE expires<=?', (time.time(),))
            try:
                db.execute('INSERT INTO billing_leases VALUES(?,?,?)', (uid, owner, time.time() + 60))
            except sqlite3.IntegrityError:
                raise RuntimeError('Billing update in progress. Refresh in a moment.') from None
        try:
            yield (uid, owner)
        finally:
            with self.store.db() as db:
                db.execute('DELETE FROM billing_leases WHERE user_id=? AND owner=?', (uid, owner))

    @contextlib.contextmanager
    def _write(self, lease):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM billing_leases WHERE user_id=? AND owner=? AND expires>?',
                              (*lease, time.time())).fetchone():
                raise RuntimeError('Billing reservation expired. Refresh status before retrying.')
            yield db

    def _user(self, uid):
        with self.store.db() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        if row is None:
            raise PermissionError('Account unavailable.')
        return dict(row)

    @staticmethod
    def _no_subscription(db, uid):
        if db.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND status IN ('active','trialing','past_due','unpaid','incomplete','paused')", (uid,)).fetchone():
            raise ValueError('An existing subscription needs attention in Manage billing.')

    def checkout(self, user, tier):
        price = self.prices.get(tier)
        if not price:
            raise ValueError('This plan is not configured.')
        uid = user['id']
        if not self._user(uid)['email_verified']:
            raise ValueError('Verify your email before starting paid checkout.')
        with self._lease(uid) as lease:
            with self._write(lease) as db:
                self._no_subscription(db, uid)
            row = self._user(uid)
            customer = row['customer']
            if not customer:
                customer = self.gateway.call('POST', 'customers', {'email': row['email'], 'metadata[user_id]': uid}, 'customer-' + uid)['id']
                if not re.fullmatch(r'cus_[A-Za-z0-9]+', str(customer)):
                    raise RuntimeError('Invalid payment customer identifier.')
                with self._write(lease) as db:
                    db.execute('UPDATE users SET customer=? WHERE id=?', (customer, uid))
            if row['checkout_id']:
                session = self.gateway.call('GET', 'checkout/sessions/' + row['checkout_id'])
                if session.get('status') == 'complete':
                    raise ValueError('Payment is processing. Refresh status; do not pay again.')
                if session.get('status') == 'open':
                    if row['checkout_tier'] != tier:
                        raise ValueError('A checkout is already open. Complete it or wait for it to expire before changing plans.')
                    return hosted_url(session.get('url'), 'checkout.stripe.com')
                if session.get('status') != 'expired':
                    raise RuntimeError('Checkout state is uncertain. Refresh status before retrying.')
                row['checkout_tier'] = None
            if row['checkout_tier'] and row['checkout_tier'] != tier:
                raise ValueError('A checkout is pending for another plan. Retry that plan to recover it.')
            generation = row['checkout_generation'] if row['checkout_tier'] else row['checkout_generation'] + 1
            # Persist the intent BEFORE POST. A crash or uncertain response reuses
            # this exact key/plan rather than creating a second payment session.
            with self._write(lease) as db:
                self._no_subscription(db, uid)
                db.execute('INSERT OR IGNORE INTO checkout_intents VALUES(?,?,?,?,?)', (uid, generation, tier, price, int(time.time())))
                intent = db.execute('SELECT * FROM checkout_intents WHERE user_id=? AND generation=?', (uid, generation)).fetchone()
                if intent['price'] != price or intent['tier'] != tier or time.time() - intent['created'] > 23 * 3600:
                    raise RuntimeError('Uncertain checkout needs provider reconciliation; no new charge session was created.')
                db.execute('UPDATE users SET checkout_id=NULL,checkout_tier=?,checkout_generation=? WHERE id=?', (tier, generation, uid))
            session = self.gateway.call('POST', 'checkout/sessions', {
                'mode': 'subscription', 'customer': customer, 'client_reference_id': uid,
                'line_items[0][price]': price, 'line_items[0][quantity]': '1',
                'subscription_data[metadata][user_id]': uid,
                'success_url': self.public_url + '/billing/success', 'cancel_url': self.public_url + '/billing/cancel',
            }, 'checkout-' + uid + '-' + str(generation))
            url = hosted_url(session.get('url'), 'checkout.stripe.com')
            with self._write(lease) as db:
                db.execute('UPDATE users SET checkout_id=? WHERE id=?', (session['id'], uid))
            return url

    def portal(self, user):
        customer = self._user(user['id'])['customer']
        if not customer:
            raise ValueError('No billing account yet. Choose a subscription first.')
        result = self.gateway.call('POST', 'billing_portal/sessions', {'customer': customer, 'return_url': self.public_url + '/billing/success'})
        return hosted_url(result.get('url'), 'billing.stripe.com')

    def _save_subscription(self, db, subscription, user_id):
        items = (subscription.get('items') or {}).get('data') or []
        chosen = next((i for i in items if (i.get('price') or {}).get('id') in self.prices.values()), None)
        price = chosen['price']['id'] if chosen else ''
        end = (chosen or {}).get('current_period_end', subscription.get('current_period_end', 0))
        if type(end) is not int:
            end = 0
        status = str(subscription.get('status', 'unknown'))
        previous = db.execute('SELECT user_id FROM subscriptions WHERE id=?', (subscription['id'],)).fetchone()
        if previous and previous['user_id'] != user_id:
            raise RuntimeError('Subscription identity mismatch.')
        db.execute('INSERT INTO subscriptions VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,period_end=excluded.period_end,price=excluded.price,cancel_at_period_end=excluded.cancel_at_period_end,checked=excluded.checked',
                   (subscription['id'], user_id, status, end, price, bool(subscription.get('cancel_at_period_end')), int(time.time())))

    def _subscription(self, sid, customer):
        if not isinstance(sid, str) or not re.fullmatch(r'sub_[A-Za-z0-9]+', sid):
            raise ValueError('Missing subscription identifier.')
        subscription = self.gateway.call('GET', 'subscriptions/' + sid)
        if subscription.get('id') != sid or subscription.get('customer') != customer:
            raise RuntimeError('Subscription identity mismatch.')
        return subscription

    def webhook(self, event):
        kind = event.get('type', '')
        if not isinstance(kind, str) or not (kind.startswith('customer.subscription.') or kind == 'checkout.session.completed'):
            return
        data = event.get('data')
        obj = data.get('object') if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            raise ValueError('Invalid webhook object.')
        sid = obj.get('subscription') if kind == 'checkout.session.completed' else obj.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'sub_[A-Za-z0-9]+', sid):
            raise ValueError('Missing subscription identifier.')
        with self.store.db() as db:
            if db.execute('SELECT 1 FROM events WHERE id=?', (event['id'],)).fetchone():
                return
            # Minimal durable inbox; never store full provider/customer payloads.
            db.execute('INSERT OR IGNORE INTO billing_inbox(id,subscription,customer,received) VALUES(?,?,?,?)',
                       (event['id'], sid, str(obj.get('customer') or ''), int(time.time())))
        self.process_event(event['id'])

    def process_event(self, event_id):
        with self.store.db() as db:
            item = db.execute('SELECT * FROM billing_inbox WHERE id=? AND processed=0', (event_id,)).fetchone()
        if not item:
            return
        try:
            customer = item['customer']
            if not customer:
                customer = self.gateway.call('GET', 'subscriptions/' + item['subscription']).get('customer')
            with self.store.db() as db:
                user = db.execute('SELECT id FROM users WHERE customer=?', (customer,)).fetchone()
            if not user:
                raise RuntimeError('Billing customer is not linked yet; event retained for retry.')
            with self._lease(user['id']) as lease:
                # Fetch within per-user ownership, but outside the DB write lock.
                # Delayed events cannot overwrite a later fetch in another worker.
                subscription = self._subscription(item['subscription'], customer)
                with self._write(lease) as db:
                    self._save_subscription(db, subscription, user['id'])
                    db.execute('UPDATE users SET checkout_id=NULL,checkout_tier=NULL WHERE id=?', (user['id'],))
                    db.execute('INSERT OR IGNORE INTO events VALUES(?,?)', (event_id, int(time.time())))
                    db.execute('UPDATE billing_inbox SET processed=1,last_error=NULL WHERE id=?', (event_id,))
                    db.execute('DELETE FROM events WHERE received<?', (int(time.time()) - 90 * 86400,))
                    db.execute('DELETE FROM billing_inbox WHERE processed=1 AND received<?', (int(time.time()) - 90 * 86400,))
        except Exception as exc:
            with self.store.db() as db:
                db.execute('UPDATE billing_inbox SET attempts=attempts+1,last_error=?,retry_at=? WHERE id=?',
                           (type(exc).__name__, int(time.time()) + 60, event_id))
            raise

    def retry_pending(self, limit=25):
        with self.store.db() as db:
            items = db.execute('SELECT id FROM billing_inbox WHERE processed=0 AND retry_at<=? AND attempts<20 ORDER BY received LIMIT ?',
                               (int(time.time()), min(100, max(1, limit)))).fetchall()
        for item in items:
            try:
                self.process_event(item['id'])
            except (RuntimeError, ValueError, httpx.HTTPError):
                continue  # durable error code/attempt count are already recorded
        return len(items)

    def refresh(self, user):
        uid = user['id']
        with self._lease(uid) as lease:
            owner = self._user(uid)
            handled = set()
            if owner['checkout_id']:
                session = self.gateway.call('GET', 'checkout/sessions/' + owner['checkout_id'])
                sid = session.get('subscription')
                if session.get('status') == 'complete' and sid:
                    subscription = self._subscription(sid, owner['customer'])
                    with self._write(lease) as db:
                        self._save_subscription(db, subscription, uid)
                        db.execute('UPDATE users SET checkout_id=NULL,checkout_tier=NULL WHERE id=?', (uid,))
                    handled.add(sid)
            with self.store.db() as db:
                rows = db.execute('SELECT id FROM subscriptions WHERE user_id=?', (uid,)).fetchall()
            for row in rows:
                if row['id'] in handled:
                    continue
                subscription = self._subscription(row['id'], owner['customer'])
                with self._write(lease) as db:
                    self._save_subscription(db, subscription, uid)
        return self.store.entitlement(uid, self.prices.values())
