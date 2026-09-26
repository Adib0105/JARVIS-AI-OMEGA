"""Desktop account client. Cloud session tokens live in memory, never chat or .env."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


def service_origin(value):
    value = str(value).strip().rstrip('/')
    parts = urlsplit(value)
    local = parts.hostname in ('127.0.0.1', 'localhost') and os.getenv('JARVIS_ALLOW_LOCAL_SERVER') == 'true'
    if (not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path
            or (parts.scheme != 'https' and not (parts.scheme == 'http' and local))):
        raise ValueError('Enter your JARVIS account server HTTPS origin. Local HTTP requires development mode.')
    return value


_active_client = None


def active_client():
    if _active_client is None or not _active_client._token:
        raise RuntimeError('Sign in to the configured JARVIS account server for commercial weather.')
    return _active_client


class SubscriptionClient:
    def __init__(self, origin):
        self.origin = service_origin(origin)
        self._token = ''

    def request(self, method, path, payload=None):
        headers = {'Authorization': 'Bearer ' + self._token} if self._token else {}
        try:
            with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
                with client.stream(method, self.origin + path, json=payload, headers=headers) as response:
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 262144:
                            raise RuntimeError('Account server response is too large.')
                    import json
                    try:
                        value = json.loads(data)
                    except ValueError:
                        raise RuntimeError('Account server returned an invalid response.') from None
                    if response.status_code == 401:
                        self._token = ''
                    if response.status_code >= 300:
                        # Never reflect a server body that might echo submitted credentials.
                        messages = {400: 'Check your details or existing subscription. Use Manage billing for plan changes.',
                                    401: 'Sign-in expired or credentials are incorrect.', 403: 'An active Pro plan is required.',
                                    429: 'Too many requests. Please wait and retry.', 503: 'Service unavailable or not configured.'}
                        raise RuntimeError(messages.get(response.status_code, 'Account server request failed.'))
                    if not isinstance(value, dict):
                        raise RuntimeError('Invalid account response.')
                    return value
        except httpx.HTTPError:
            raise RuntimeError('Cannot reach the account server. Check the URL and internet connection.') from None

    def sign_in(self, email, password, *, name=None):
        body = {'email': email, 'password': password}
        if name is not None:
            body['name'] = name
        value = self.request('POST', '/auth/register' if name is not None else '/auth/login', body)
        token = value.get('access_token')
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise RuntimeError('Account server did not return a valid session.')
        self._token = token
        result = self.request('GET', '/me')
        global _active_client
        _active_client = self
        return result

    def sign_out(self):
        try:
            if self._token:
                self.request('POST', '/auth/logout', {})
        finally:
            self._token = ''

    def payment_link(self, plan=None):
        result = self.request('POST', '/billing/checkout' if plan else '/billing/portal', {'plan': plan} if plan else {})
        url = result.get('url', '')
        parts = urlsplit(url)
        expected = 'checkout.stripe.com' if plan else 'billing.stripe.com'
        if parts.scheme != 'https' or parts.hostname != expected or parts.username or parts.password or parts.port not in (None, 443):
            raise RuntimeError('Unexpected payment URL.')
        return url
