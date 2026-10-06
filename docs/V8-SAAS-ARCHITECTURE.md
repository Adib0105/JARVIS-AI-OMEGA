# V8 SaaS architecture — implementation contract

2026-10-06. **Design only; the AI SaaS service is not implemented or deployed.**
This is the next-phase design over the existing account/billing service. It is
not evidence that authentication, billing or provider calls work in production.
The P0 and physical acceptance limits in the adjacent reports still apply.

## Boundaries and existing owners

Keep `server.app:create_app`, `Store`, `Billing`, recovery and the durable billing
worker. Do not create another user table, payment webhook receiver or login flow.
Keep local profiles and the desktop `RecordingToolRegistry` independent of online
identity. Server authorization cannot grant local file, microphone or UI control
permission; a local approval cannot grant an owner-funded server entitlement.

| Boundary | Existing owner | V8 extension |
|---|---|---|
| Local identity/history | `user_profiles.py`, local memory stores | Display local and online identities separately; no automatic history merge |
| Online accounts/sessions | `server/store.py`, `recovery.py`, `app.py` | Session/device controls, suspension, recovery codes, deletion lifecycle |
| Billing truth | `server/billing.py`, `worker.py` | Configured plan/price mapping and invoice reconciliation |
| Entitlement authority | `Store.entitlement()` | One server policy service over versioned plan/feature/model/usage definitions |
| AI execution | Desktop provider adapters today | New server gateway; a desktop gateway adapter preserves the existing provider interface |
| Local action authority | Permission/capability/effect/audit/verification layers | Retained for every proposed tool action, regardless of remote model or plan |
| Metering/cost authority | Missing | Transactional reservations, request ledger and owner budgets on the server |
| Owner administration | Missing | Separate privileged API, audited controls and secret-free dashboard |

The client has two explicit operating modes. **Personal/local** uses the user's
own credentials or a local model. **JARVIS online** uses an opaque account session
and calls only the configured JARVIS HTTPS origin. No failure silently switches
to another paid provider or billing identity. Local configuration never enables
owner-funded features. No owner provider secret is shipped in the desktop,
package, response, logs, backup export intended for users or model context.

## Module and API changes

Extend the existing server package with `migrations.py`, `entitlements.py`,
`usage.py`, `ai_gateway.py`, `model_catalog.py` and server-only provider adapters.
These modules must not import `jarvis.config`, local history, filesystem tools or
desktop provider instances. Extract a small neutral turn/usage contract if needed;
do not duplicate the agent runtime inside the API server. Keep blocking hashing,
database and provider work off the FastAPI event loop, with bounded concurrency.

Preserve existing `/auth/*`, `/me`, `/billing/*`, weather and health contracts.
Add versioned `/v1/*` routes for the new product surface; map old `/me` weather
subscription fields through the same policy service during migration.

| Proposed route | Required behavior before use |
|---|---|
| `GET /v1/me`, `GET /v1/me/entitlements` | Server identity, effective policy/version and finite allowances; no secret data |
| `GET /v1/me/sessions`, `DELETE /v1/me/sessions/{id}` | User-owned random session IDs, coarse device metadata; never return token digests or authorize by device labels |
| `POST /v1/me/logout-all` | Revoke all sessions atomically; invalidate remembered desktop session after rejection |
| `POST /v1/me/recovery-codes` | Recent credential proof; rotate hashed, single-use codes; show plaintext once without logging |
| `POST /v1/me/deletion` | Recent credential proof; revoke sessions, disable paid calls, persist deletion/cancellation work |
| `GET /v1/plans`, `GET /v1/me/usage` | Sanitized active catalog and committed/reserved/remaining usage; no fabricated values |
| `POST /v1/ai/requests` | Authenticated, bounded, idempotent gateway request; derived policy/route/cost authority |
| `GET /v1/ai/requests/{id}`, `POST /v1/ai/requests/{id}/cancel` | User-scoped status/cancellation; cancellation acknowledgement is not proof of zero provider cost |
| `/v1/admin/*` | Separate privileged role, recent reauthentication, least-privilege operation checks and durable audit |

Request bodies cannot select a user, plan, price, provider key, arbitrary provider
URL or unrestricted model. A feature/task hint is advisory and must agree with
the payload and server policy. Enforce typed tool schema/message/image limits;
tool requests returned by a model remain untrusted data for the desktop gate.
The gateway never executes the user's local tools. Start with bounded non-streaming
responses; add streaming only after disconnect and usage-finalization tests pass.

## Account and migration contract

Introduce ordered, checksum-verified schema migrations over the existing SQLite
database. Back up and rehearse upgrade/restore against the current schema before
applying to a real deployment. Migrations are transactional, restart-safe and
fail startup on an unknown future version or checksum mismatch. Do not run
destructive automatic down-migrations or use table recreation as an upgrade.

Extend `users` with account status and an authorization version. Give existing
sessions random public IDs, creation/last-seen/recent-auth timestamps and bounded
untrusted device labels. Keep opaque high-entropy tokens and hashed token records;
no stateless role/plan cache that survives revocation. Current password-reset and
password-change revocation must still invalidate every session and recovery token.
Do not bypass email verification for paid service.

Audit failed/repeated logins without storing passwords/tokens. Rate-limit by both
account and connection source; forward proxy headers are trusted only from an
explicit deployment allowlist. Suspicious-login detection initially records coarse
new-device/repeated-failure events and revokes/escalates according to policy; it
must not pretend to perform reliable geolocation or device attestation.

Deletion is a durable state machine: disable and revoke, reconcile/cancel billing,
delete user-owned service data, then retain only explicitly documented required
accounting/security records under retention rules. Failures retry from the same
job. Do not report full deletion while provider-side subscription cancellation or
required cleanup is unresolved. Local history deletion is a separate explicit
desktop operation. Test one user's deletion against another user's data.

## Configurable plans and role separation

Store immutable policy revisions with active pointers: `plans`, `plan_features`,
`plan_models`, `plan_usage_policies`, `model_catalog`, `provider_catalog`,
`billing_prices` and audited `user_roles`. Numeric limits are finite nonnegative
integers with schema validation; an unknown/disabled policy denies service.
Exact model IDs, providers, prices and amounts are deployment configuration, not
invented defaults. Free owner-funded service is disabled until a budget is set.

| Product label | Authority |
|---|---|
| FREE | Configured basic feature/model set, finite request/token/cost limits |
| PRO | Trusted paid subscription or expiring audited grant mapped to a policy revision |
| ADVANCED | Separate trusted mapping with stronger configured models/features and finite higher budgets |
| ADMIN | Operator-assigned role over an explicit service policy; never purchasable or self-selectable |

An admin role authorizes management operations, not unlimited provider spend or
unapproved local actions. Separate admin service budgets and provider-wide owner
caps still apply. Bootstrap the first administrator through a local operator
command with explicit identity, then record every role/grant change; no public
registration parameter or checkout price can make an administrator.

Effective entitlement combines active account, email verification, role, trusted
subscription/grant, policy revision, feature and model restrictions. Any unknown,
expired, disabled or stale input denies paid usage or downgrades to the configured
FREE policy. UI visibility is a presentation of this result, never its authority.
Subscription expiry/revocation is rechecked at admission and immediately before
provider dispatch; active in-flight requests remain metered under their admitted
policy revision. New requests see the new policy immediately.

## Admission, routing and bounded cost

Use one server request ID scoped by user and an idempotency key plus canonical
payload hash. Reusing a key with different content is a conflict. Keep raw prompts
out of the usage/audit ledger; any short-lived response cache needs explicit
encryption, expiry and deletion policy. Requests never share cached user content.

Admission sequence: authenticate, validate account/subscription, authorize feature,
bound/validate content, classify task, intersect eligible routes with allowed
models, calculate worst-case token/cost reservation, then atomically reserve.
Classification can narrow access and cost, never widen either. FAST/SMART/VISION/
CODING/RESEARCH/LOCAL/FALLBACK are logical routes over a versioned server catalog.
LOCAL remains an explicit desktop mode, not a server fallback into desktop tools.

The reservation transaction checks per-user request, UTC-day and UTC-month token/
cost budgets, concurrent leases, rate limits and provider/owner aggregate caps.
Use integer billing units and versioned input/output pricing, never floating-point
money. Bound input using the selected tokenizer or a conservative adapter contract
and enforce provider output caps. Unsupported/unbounded modalities or unknown
pricing/usage semantics are disabled. User budget resets do not reset the owner's
global spend cap. Account/plan policy is revalidated within admission to prevent
concurrent downgrade or suspension races.

Persist `RESERVED` before network dispatch and `DISPATCHING` immediately before
the call. Keep the database transaction short; do not hold a write lock during
provider I/O. Finalize exactly once with observed usage, latency, model/provider,
feature, plan/policy version, status and reconciliation evidence. Convert the
reservation to committed usage and release only proven-unused budget. A timeout,
crash, disconnect or ambiguous provider error is `UNKNOWN`, not a refund.
Conservative liability remains charged/reserved until authoritative reconciliation.
Quota accounting belongs to the admission day/month so requests crossing midnight
cannot double-release or escape a budget. Expiring a concurrency lease alone must
not authorize overlap with a provider request whose termination is unconfirmed.

Idempotent retry returns/reconciles the existing request. Fallback may dispatch
only when the prior adapter proves no provider execution occurred, or under a
provider idempotency contract tested for that adapter. Never make a second paid
call after uncertain first dispatch. Cancellation is best effort after dispatch;
retain usage liability and report actual terminal/unknown state. Recovery workers
reconcile crashed requests and alarm on stuck liability; they do not silently
erase records or restart unknown calls. Provider circuit breakers are shared by
the gateway workers and cannot skip authorization or reservation.

Only operator-configured HTTPS provider endpoints and credential references are
allowed. Do not fetch arbitrary image/file URLs supplied by a user or provider.
Require bounded uploaded content and an explicit supported modality. Sanitize
upstream errors; credentials, raw headers, private prompts and bearer tokens never
appear in user errors, analytics or dashboard screens.

## Billing, admin and rollout

Extend the existing signed webhook verification, durable inbox, ownership checks,
per-user lease and provider-state reconciliation. Map trusted price IDs to plan
and interval; unknown prices confer no premium access. Do not replace the current
idempotent checkout-intent flow. A return/success URL cannot activate a plan.
Persist invoice identity/state separately from entitlement and reconcile renewals,
upgrade/downgrade, cancellation, expiration, trial and payment-failure events.
Out-of-order/replayed events must converge on verified provider state. Define
scheduled downgrade timing explicitly and preserve the existing fail-closed policy
until a tested grace policy is deliberately configured.

Admin dashboards read real, aggregated ledgers. Revenue comes from reconciled paid
invoices; provider cost comes from known usage with unknown liabilities displayed
separately. Profit is explicitly estimated and must not treat missing provider
cost as zero. Provider management accepts secret references through privileged
deployment controls, not a secret-returning dashboard endpoint. Suspend/restore,
plan grants, subscription extensions and session revocation require reason,
actor, target, authorization and immutable audit evidence.

First deploy as a single-host account/gateway service with SQLite WAL and finite
worker limits. This is not a distributed database design. Do not enable multiple
independent hosts against copied SQLite files; migrate and prove transactional
quota/concurrency semantics in a shared production database before horizontal
scaling. Separate account, billing and AI credentials; provide per-provider kill
switches and global spending disablement. Backups, restore, monitoring, host/TLS,
SMTP and merchant/provider sandbox access are deployment gates, not fake fixtures.

## Build order and acceptance evidence

| Increment | Required evidence before promotion |
|---|---|
| Versioned migrations/account lifecycle | Upgrade current database, repeat/restart, rollback/restore rehearsal, hash/session revocation, deletion isolation, device ownership and concurrency races |
| Plans/entitlements | Every plan-feature-model matrix row, forged local/user/plan inputs, unknown prices, stale subscription, suspension, expiry, admin assignment and existing weather compatibility |
| Gateway/metering/router | Real HTTP path with controlled adapters; concurrent duplicate/limit races, all dispatch crash points, fallback uncertainty, cancellation, midnight/month change, unavailable pricing and global owner caps |
| Live provider sandbox | Configured owner-approved bounded budgets, authoritative usage/cost reconciliation, real timeouts/rate limits and credential-redaction evidence |
| Billing extensions | Signed/replayed/out-of-order events, durable recovery, invoice/customer ownership, every lifecycle state, merchant sandbox end-to-end |
| Desktop/admin integration | Real server-backed status/errors/allowances; per-user isolation; local permission/audit/verification retained; unauthorized admin calls rejected |
| Production promotion | Physical Windows P0 acceptance, clean install/upgrade/rollback, security/privacy review, backend load/backup/restore/alerts and all requested release gates |

Failure injection and local HTTP/SQLite tests establish implementation behavior;
they do not prove live provider cost, merchant billing or deployed availability.
The next coding increment is the existing account service's migration/session/
deletion lifecycle. This document changes no database, subscription, credentials,
service configuration or production deployment. Rollback is a normal Git revert.
