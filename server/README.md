# JARVIS account and subscription server

This is a runnable backend integration. It is not deployed by installing the desktop application. The owner supplies a payment-provider account, recurring prices, a public HTTPS origin and a licensed commercial weather key. No default account/password or merchant keys ship with JARVIS.

## Run locally

```bash
python -m venv .venv-server
.venv-server/bin/python -m pip install -r requirements-server.txt
.venv-server/bin/python -m uvicorn server.app:create_app --factory --host 127.0.0.1 --port 8000
```

On Windows, use `.venv-server\Scripts\python.exe` instead. Test account registration through the desktop by setting `JARVIS_ALLOW_LOCAL_SERVER=true` and entering `http://127.0.0.1:8000` in the subscription tab. Billing remains unavailable until configured. No card data is collected by this backend.

Run tests: `python -m unittest discover -s tests_server -v`.

## Deployment configuration

Load values from `server/.env.example` into the process environment through your host's secret manager. This module does not automatically read that file. Bind Uvicorn to loopback behind an HTTPS reverse proxy. Use a private, persistent directory for `JARVIS_SERVER_DB`; back it up. The SQLite implementation is for one host, not a horizontally distributed cluster. At present rate limits use the direct client address; set an appropriate trusted proxy configuration before operating behind a proxy.

1. Set `JARVIS_PUBLIC_URL` to the final HTTPS origin.
2. Configure Stripe recurring monthly/yearly Price IDs and the secret API key. Prices are chosen on the server; no amount supplied by the desktop is accepted.
3. Enable Stripe's Customer Portal with the intended cancellation, plan-change and invoice settings.
4. Add `/billing/webhook` as the signed endpoint for `checkout.session.completed` and `customer.subscription.created/updated/deleted/paused/resumed`; store its signing secret. The integration pins Stripe API `2025-03-31.basil`, reads billing periods from items and accepts the earlier top-level period as a compatibility fallback.
5. Set `OPEN_METEO_API_KEY` on the backend. Commercial desktop distributions set `JARVIS_COMMERCIAL_WEATHER=true` and `JARVIS_ACCOUNT_SERVER` to the origin; weather/geocoding requests then use the authenticated backend. Do not put a shared merchant weather key or Stripe secret in the installer.
6. Exercise test-mode checkout, webhook delivery/retry, renewal, failed payment, cancellation and portal return before enabling real charges. Verify hosting/provider account eligibility separately.

## Behavior

- Registration/login uses salted PBKDF2-SHA256, opaque random session tokens and hashed server session records. Password change revokes all sessions. Registration/login/other API calls are rate-limited; repeated password failures lock the account temporarily.
- Stripe-hosted checkout handles card entry. Pending checkout sessions are reused, and an existing live/delinquent subscription directs the user to the portal instead of a second subscription.
- The success page never grants access. Signed webhook events are replay-checked transactionally and reconcile against current Stripe subscription state, so a late event cannot restore a canceled subscription.
- Only configured product prices in active/trialing state, with a future billing-period expiry and recent verification, grant Pro. Past-due/unpaid/incomplete/paused/canceled subscriptions fail closed.
- `/pro/forecast` refreshes current provider state on each request and checks the authenticated account's entitlement. `/weather/report` and `/weather/cities` are authenticated free-plan endpoints for commercial deployments.
- Desktop cloud tokens are memory-only. No passwords, card details, tokens or webhook bodies are written to application logs. Configure reverse-proxy logs to omit authorization headers and request bodies as well.

## Before public sale

This change does not implement email verification, forgotten-password recovery, fraud handling, tax policy, customer support operations or distributed service scaling. Complete those with the target merchant/hosting setup. The repository's existing production audit and real-PC Windows checklist remain required. Keep automatic public release publication disabled until those independent gates are resolved.
