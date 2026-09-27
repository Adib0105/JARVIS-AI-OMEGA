"""Fixed Stripe API origins, hosted payments and signed webhook reconciliation."""
from __future__ import annotations

import hashlib
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
    def __init__(self, store, gateway, prices, public_url):
        self.store, self.gateway, self.prices, self.public_url = store, gateway, prices, public_url

    def checkout(self, user, tier):
        price = self.prices.get(tier)
        if not price:
            raise ValueError('This plan is not configured.')
        with self.store.db() as db:
            # Serializes checkout retries and webhook reconciliation across workers.
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
            if db.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND status IN ('active','trialing','past_due','unpaid','incomplete','paused') ", (user['id'],)).fetchone():
                raise ValueError('An existing subscription needs attention in Manage billing.')
            customer = row['customer']
            if not customer:
                customer = self.gateway.call('POST', 'customers', {'email': user['email'], 'metadata[user_id]': user['id']}, 'customer-' + user['id'])['id']
                db.execute('UPDATE users SET customer=? WHERE id=?', (customer, user['id']))
            if row['checkout_id']:
                session = self.gateway.call('GET', 'checkout/sessions/' + row['checkout_id'])
                if session.get('status') == 'complete':
                    raise ValueError('Payment is processing. Refresh status; do not pay again.')
                if session.get('status') == 'open':
                    if row['checkout_tier'] != tier:
                        raise ValueError('A checkout is already open. Complete it or wait for it to expire before changing plans.')
                    return hosted_url(session.get('url'), 'checkout.stripe.com')
            generation = row['checkout_generation'] + 1
            session = self.gateway.call('POST', 'checkout/sessions', {
                'mode': 'subscription', 'customer': customer, 'client_reference_id': user['id'],
                'line_items[0][price]': price, 'line_items[0][quantity]': '1',
                'subscription_data[metadata][user_id]': user['id'],
                'success_url': self.public_url + '/billing/success', 'cancel_url': self.public_url + '/billing/cancel',
            }, 'checkout-' + user['id'] + '-' + str(generation))
            url = hosted_url(session.get('url'), 'checkout.stripe.com')
            db.execute('UPDATE users SET checkout_id=?,checkout_tier=?,checkout_generation=? WHERE id=?', (session['id'], tier, generation, user['id']))
            return url

    def portal(self, user):
        if not user['customer']:
            raise ValueError('No billing account yet. Choose a subscription first.')
        result = self.gateway.call('POST', 'billing_portal/sessions', {'customer': user['customer'], 'return_url': self.public_url + '/billing/success'})
        return hosted_url(result.get('url'), 'billing.stripe.com')

    def _save_subscription(self, db, subscription, user_id):
        items = (subscription.get('items') or {}).get('data') or []
        chosen = next((i for i in items if (i.get('price') or {}).get('id') in self.prices.values()), None)
        price = chosen['price']['id'] if chosen else ''
        # Basil and later expose the billing period on subscription items.
        end = (chosen or {}).get('current_period_end', subscription.get('current_period_end', 0))
        if type(end) is not int:
            end = 0
        status = str(subscription.get('status', 'unknown'))
        db.execute('INSERT INTO subscriptions VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,period_end=excluded.period_end,price=excluded.price,cancel_at_period_end=excluded.cancel_at_period_end,checked=excluded.checked',
                   (subscription['id'], user_id, status, end, price, bool(subscription.get('cancel_at_period_end')), int(time.time())))

    def webhook(self, event):
        kind = event.get('type', '')
        if not isinstance(kind, str) or not (kind.startswith('customer.subscription.') or kind == 'checkout.session.completed'):
            return
        event_data = event.get('data')
        obj = event_data.get('object') if isinstance(event_data, dict) else None
        if not isinstance(obj, dict):
            raise ValueError('Invalid webhook object.')
        sid = obj.get('subscription') if kind == 'checkout.session.completed' else obj.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'sub_[A-Za-z0-9]+', sid):
            raise ValueError('Missing subscription identifier.')
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM events WHERE id=?', (event['id'],)).fetchone():
                return
            # Fetch current Stripe state instead of trusting delayed/out-of-order event bodies.
            subscription = self.gateway.call('GET', 'subscriptions/' + sid)
            user = db.execute('SELECT id FROM users WHERE customer=?', (subscription.get('customer'),)).fetchone()
            if user:
                self._save_subscription(db, subscription, user['id'])
                db.execute('UPDATE users SET checkout_id=NULL,checkout_tier=NULL WHERE id=?', (user['id'],))
            db.execute('INSERT INTO events VALUES(?,?)', (event['id'], int(time.time())))
            db.execute('DELETE FROM events WHERE received<?', (int(time.time()) - 90 * 86400,))

    def refresh(self, user):
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            owner = db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
            if owner['checkout_id']:
                session = self.gateway.call('GET', 'checkout/sessions/' + owner['checkout_id'])
                sid = session.get('subscription')
                if session.get('status') == 'complete' and isinstance(sid, str) and re.fullmatch(r'sub_[A-Za-z0-9]+', sid):
                    subscription = self.gateway.call('GET', 'subscriptions/' + sid)
                    if subscription.get('customer') != owner['customer']:
                        raise RuntimeError('Subscription identity mismatch.')
                    self._save_subscription(db, subscription, user['id'])
                    db.execute('UPDATE users SET checkout_id=NULL,checkout_tier=NULL WHERE id=?', (user['id'],))
            rows = db.execute('SELECT id FROM subscriptions WHERE user_id=?', (user['id'],)).fetchall()
            for row in rows:
                subscription = self.gateway.call('GET', 'subscriptions/' + row['id'])
                if subscription.get('customer') != user['customer']:
                    raise RuntimeError('Subscription identity mismatch.')
                self._save_subscription(db, subscription, user['id'])
        return self.store.entitlement(user['id'], self.prices.values())
