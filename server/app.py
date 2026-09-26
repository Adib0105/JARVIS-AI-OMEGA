"""Run with: uvicorn server.app:create_app --factory --host 127.0.0.1.

Deploy behind HTTPS; secrets live only on this backend. No card details enter JARVIS.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool

from .billing import Billing, StripeGateway, verify_event
from .store import Store


def field(body, key, low=1, high=256):
    value = body.get(key)
    if not isinstance(value, str) or not low <= len(value) <= high or '\0' in value:
        raise ValueError(f'Invalid {key}.')
    return value


def email(body):
    value = field(body, 'email', 3, 254).strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('Enter a valid email address.')
    return value


async def body_bytes(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise ValueError('Request is too large.')
    return bytes(raw)


async def body_json(request):
    body = json.loads(await body_bytes(request))
    if not isinstance(body, dict):
        raise ValueError('JSON object required.')
    return body


def create_app(*, db_path=None, gateway=None, config=None):
    config = dict(os.environ if config is None else config)
    public_url = config.get('JARVIS_PUBLIC_URL', 'http://127.0.0.1:8000').rstrip('/')
    parts = urlsplit(public_url)
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path or (parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1'))):
        raise ValueError('JARVIS_PUBLIC_URL must be an HTTPS origin (HTTP loopback only for development).')
    app = FastAPI(title='JARVIS Accounts & Subscriptions', docs_url=None, redoc_url=None)
    store = Store(db_path or config.get('JARVIS_SERVER_DB', './server-data/accounts.sqlite3'))
    prices = {name: config.get('STRIPE_PRICE_' + name.upper(), '') for name in ('monthly', 'yearly')}
    prices = {k: v for k, v in prices.items() if v}
    billing = Billing(store, gateway or StripeGateway(config.get('STRIPE_SECRET_KEY', '')), prices, public_url)
    app.state.store, app.state.billing = store, billing

    @app.middleware('http')
    async def headers_and_limits(request, call_next):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != public_url:
            return JSONResponse({'detail': 'Origin is not allowed.'}, status_code=403)
        ip = request.client.host if request.client else 'unknown'
        path = request.url.path
        # Webhooks must stay available to retries; verification provides their auth.
        if path != '/billing/webhook':
            limit, seconds = (5, 3600) if path == '/auth/register' else (20, 60) if path.startswith('/auth/') else (120, 60)
            if not await run_in_threadpool(store.rate, ('register' if path == '/auth/register' else 'auth' if path.startswith('/auth/') else 'api') + ':' + ip, limit, seconds):
                return JSONResponse({'detail': 'Too many requests. Please retry later.'}, status_code=429)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        # JSON decoder errors may contain input fragments; don't reflect credentials.
        detail = 'Invalid request.' if isinstance(exc, json.JSONDecodeError) else str(exc)
        return JSONResponse({'detail': detail}, status_code=400)

    @app.exception_handler(PermissionError)
    async def unauthorized(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=401)

    @app.exception_handler(RuntimeError)
    @app.exception_handler(sqlite3.Error)
    async def unavailable(request, exc):
        return JSONResponse({'detail': 'Service temporarily unavailable or not configured.'}, status_code=503)

    def token(request):
        value = request.headers.get('authorization', '')
        if not value.startswith('Bearer '):
            raise PermissionError('Sign in required.')
        return value[7:]

    async def user(request):
        return await run_in_threadpool(store.user, token(request))

    @app.get('/health')
    def health():
        with store.db() as db:
            db.execute('SELECT 1').fetchone()
        return {'status': 'ok', 'billing_configured': bool(prices and config.get('STRIPE_SECRET_KEY') and config.get('STRIPE_WEBHOOK_SECRET'))}

    @app.post('/auth/register')
    async def register(request: Request):
        body = await body_json(request)
        name = ' '.join(field(body, 'name', 1, 60).split())
        if not name:
            raise ValueError('Name is required.')
        return await run_in_threadpool(store.register, email(body), name, field(body, 'password', 12, 256))

    @app.post('/auth/login')
    async def login(request: Request):
        body = await body_json(request)
        return await run_in_threadpool(store.login, email(body), field(body, 'password', 1, 256))

    @app.post('/auth/logout')
    async def logout(request: Request):
        await run_in_threadpool(store.logout, token(request))
        return {'ok': True}

    @app.post('/auth/password')
    async def password(request: Request):
        who = await user(request)
        body = await body_json(request)
        await run_in_threadpool(store.change_password, who['id'], field(body, 'current_password'), field(body, 'new_password', 12, 256))
        return {'ok': True, 'sign_in_required': True}

    @app.get('/me')
    async def me(request: Request):
        who = await user(request)
        entitlement = await run_in_threadpool(store.entitlement, who['id'], prices.values())
        return {'email': who['email'], 'name': who['name'], 'subscription': entitlement, 'plans': list(prices)}

    @app.post('/billing/checkout')
    async def checkout(request: Request):
        who = await user(request)
        body = await body_json(request)
        return {'url': await run_in_threadpool(billing.checkout, who, field(body, 'plan', 1, 20))}

    @app.post('/billing/portal')
    async def portal(request: Request):
        return {'url': await run_in_threadpool(billing.portal, await user(request))}

    @app.post('/billing/refresh')
    async def refresh(request: Request):
        return await run_in_threadpool(billing.refresh, await user(request))

    @app.post('/billing/webhook')
    async def webhook(request: Request):
        raw = await body_bytes(request)
        event = verify_event(raw, request.headers.get('stripe-signature', ''), config.get('STRIPE_WEBHOOK_SECRET', ''))
        await run_in_threadpool(billing.webhook, event)
        return {'received': True}

    @app.post('/weather/cities')
    async def cities(request: Request):
        await user(request)
        if not config.get('OPEN_METEO_API_KEY'):
            raise RuntimeError('Commercial weather is not configured.')
        body = await body_json(request)
        from jarvis.daily_briefing import find_locations
        return {'results': await run_in_threadpool(find_locations, field(body, 'city', 2, 100))}

    @app.post('/weather/report')
    async def weather(request: Request):
        await user(request)
        if not config.get('OPEN_METEO_API_KEY'):
            raise RuntimeError('Commercial weather is not configured.')
        body = await body_json(request)
        from jarvis.daily_briefing import valid_location, rich_weather_report, weather_report, air_report
        if not valid_location(body) or len(body['name']) > 100:
            raise ValueError('Select a valid city.')
        mode = body.get('mode', 'today')
        if mode == 'today':
            report = await run_in_threadpool(rich_weather_report, body)
        elif mode == 'tomorrow':
            report = await run_in_threadpool(weather_report, body, mode='tomorrow')
        elif mode == 'air':
            report = await run_in_threadpool(air_report, body)
        else:
            raise ValueError('Use Pro forecast for extended forecasts.')
        return {'report': report}

    @app.post('/pro/forecast')
    async def forecast(request: Request):
        who = await user(request)
        entitlement = await run_in_threadpool(billing.refresh, who)
        if 'extended_forecast' not in entitlement['features']:
            return JSONResponse({'detail': 'An active Pro subscription is required.'}, status_code=403)
        body = await body_json(request)
        from jarvis.daily_briefing import valid_location, weather_report
        if not valid_location(body) or len(body['name']) > 100:
            raise ValueError('Select a valid city.')
        if not config.get('OPEN_METEO_API_KEY'):
            raise RuntimeError('Commercial weather is not configured.')
        return {'report': await run_in_threadpool(weather_report, body, mode='week')}

    @app.get('/billing/success', response_class=HTMLResponse)
    def success():
        return '<h1>Return to JARVIS</h1><p>Choose Refresh subscription. Access activates only after the payment provider confirms your subscription.</p>'

    @app.get('/billing/cancel', response_class=HTMLResponse)
    def cancel():
        return '<h1>Checkout closed</h1><p>Return to JARVIS whenever you are ready.</p>'

    return app
