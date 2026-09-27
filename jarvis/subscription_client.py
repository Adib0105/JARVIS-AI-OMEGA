"""Desktop account client; optional Windows DPAPI remember-device storage per profile."""
from __future__ import annotations

import os
import json
import time
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
    global _active_client
    if _active_client is None:
        _active_client = restore_session()
    if _active_client is None or not _active_client._token:
        raise RuntimeError('Sign in to the configured JARVIS account server for commercial weather.')
    return _active_client


def session_path():
    from .config import settings
    return settings.db_path.parent / 'online-session.json'


def restore_session():
    from .local_secrets import reveal, PREFIX
    try:
        data = json.loads(session_path().read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not str(data.get('token', '')).startswith(PREFIX) or data.get('expires', 0) <= time.time():
            return None
        client = SubscriptionClient(data['origin'])
        client._token = reveal(data['token'])
        if not 20 <= len(client._token) <= 256:
            return None
        client.expires_at, client.remember = data['expires'], True
        client.display_name = str(data.get('name', ''))[:60]
        client.use_online_name = data.get('use_online_name') is True
        return client
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return None


def greeting_name(local_name):
    try:
        client = active_client()
        if client.use_online_name and client.display_name and client.expires_at > time.time():
            return client.display_name
    except RuntimeError:
        pass
    return local_name


class SubscriptionClient:
    def __init__(self, origin):
        self.origin = service_origin(origin)
        self._token = ''
        self.expires_at = 0
        self.remember = False
        self.use_online_name = False
        self.display_name = ''

    def _persist(self):
        from .user_profiles import _atomic_json
        from .local_secrets import protect, PREFIX
        from .file_mutex import locked_file
        path = session_path()
        with locked_file(path):
            if self.remember and self._token:
                protected = protect(self._token)
                if not protected.startswith(PREFIX):
                    raise RuntimeError('Remember online sign-in requires Windows credential protection.')
                _atomic_json(path, {'origin': self.origin, 'token': protected, 'expires': self.expires_at,
                                    'name': self.display_name, 'use_online_name': self.use_online_name})
            elif path.exists():
                path.unlink()

    def request(self, method, path, payload=None):
        sent_token = self._token
        headers = {'Authorization': 'Bearer ' + sent_token} if sent_token else {}
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
                    if response.status_code == 401 and self._token == sent_token:
                        self._token = ''
                        if self.remember:
                            self._persist()
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

    def sign_in(self, email, password, *, name=None, remember=False, use_online_name=False):
        if remember and os.name != 'nt':
            raise RuntimeError('Remember online sign-in requires Windows credential protection.')
        body = {'email': email, 'password': password}
        if name is not None:
            body['name'] = name
        value = self.request('POST', '/auth/register' if name is not None else '/auth/login', body)
        token = value.get('access_token')
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise RuntimeError('Account server did not return a valid session.')
        self._token = token
        expiry = value.get('expires_at')
        self.expires_at = min(expiry, time.time() + 7 * 86400) if type(expiry) is int else time.time()
        self.remember, self.use_online_name = bool(remember), bool(use_online_name)
        try:
            result = self.request('GET', '/me')
            self.display_name = ' '.join(str(result.get('name', '')).split())[:60]
            self._persist()
        except Exception:
            self._token = ''
            self.expires_at = 0
            self.remember = False
            raise
        global _active_client
        _active_client = self
        return result

    def sign_out(self):
        try:
            if self._token:
                self.request('POST', '/auth/logout', {})
        finally:
            self._token = ''
            self._persist()

    def payment_link(self, plan=None):
        result = self.request('POST', '/billing/checkout' if plan else '/billing/portal', {'plan': plan} if plan else {})
        url = result.get('url', '')
        parts = urlsplit(url)
        expected = 'checkout.stripe.com' if plan else 'billing.stripe.com'
        if parts.scheme != 'https' or parts.hostname != expected or parts.username or parts.password or parts.port not in (None, 443):
            raise RuntimeError('Unexpected payment URL.')
        return url
