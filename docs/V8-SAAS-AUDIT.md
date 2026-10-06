# JARVIS V8 feature audit and execution plan

Date: 2026-10-06. Baseline: `main@83b7f34b67c0aca444c1139cd7db700364bc554c`.
Target branch: `v8-saas-smart-jarvis`. Release decision: **HOLD**.

This is an audit of the checked-out mainline, not a claim that the requested V8
product exists. The existing draft PR #24 contains an earlier frontier audit;
its findings are leads, not verification evidence for this change. No mainline
merge, public release, merchant charge or production deployment is authorized by
this report. The development branch is independently reviewable.

## 1. Current architecture

- `desktop_app.py` dispatches frozen child modes before profile/GUI startup,
  acquires a desktop instance, selects a local profile, installs UI/runtime
  extensions and starts Tk. `main.py` is the CLI entry point.
- `jarvis/core.py:JarvisOmega` extends `core_v7.py:JarvisOmega`; this is deliberate
  compatibility inheritance. It connects layered memory, recorded tools,
  missions, provider observation, model routing, evaluation and skills.
- `RecordingToolRegistry` wraps schema validation, capability permissions,
  side-effect accounting, audit and sanitized tool evidence. Mission execution
  adds a persisted state machine, budget, retry policy and effect ledger.
- SQLite stores local profile history/memory/missions and the separate online
  account database. They are not one shared multi-tenant AI database.
- Browser reading uses public-target validation; low-level desktop operations
  remain distinct from the experimental UIA/OCR semantic action engine.
- Release/self-development uses worktrees, bounded change policies, approval and
  history-preserving rollback. A Git worktree is **not** an OS execution sandbox.

Inventory: 152 Python files / 23,601 lines under `jarvis`, seven / 837 under
`server`, 72 / 6,423 under `tests`, two / 438 under `tests_server` at baseline.
Inventory is not a statement that every line or every possible path is verified.

## 2. Existing subscription and billing

`server/billing.py` implements Stripe checkout/portal, configured monthly/yearly
prices, signed webhooks, replay records, durable inbox retries, per-user leases,
idempotent checkout intents and reconciliation with the current provider state.
It checks customer/subscription ownership. The callback success page grants no
entitlement. Delinquency, unknown prices, expiry and stale checks fail closed.

`Store.entitlement()` currently hardcodes `free`/`pro` and one paid feature:
`extended_forecast`. Monthly/yearly are billing intervals, not configurable V8
product plans. There is no Advanced/Admin AI plan model, feature-policy table,
AI token allowance or application invoice ledger. The provider-hosted portal
handles billing management. Do not create a competing webhook/account service.

## 3. Existing authentication

Local accounts (`user_profiles.py`) select separate local data/preferences and
OAuth paths. Online accounts (`server/store.py`, `recovery.py`, `app.py`) use
salted PBKDF2-SHA256 (600,000 rounds), random bearer tokens with hashed database
records, expiration, password lockout and session revocation on password reset.
Verification/reset codes are hashed, expire and are single-use. SMTP delivery
requires configuration. The desktop subscription token is memory-only unless the
operator opts into Windows DPAPI protection.

Missing from the requested online lifecycle: account deletion, a device/session
management API/UI, admin suspension/roles, suspicious-login event handling and a
recovery-code lifecycle distinct from email-reset codes. Local login is not proof
of a cloud entitlement, and cloud sign-in must not merge local histories.

## 4. Existing provider/model router

`providers/base.py` defines normalized turns and tool calls. OpenAI,
OpenRouter and local adapters are selected by `factory.py`; `ModelRouter` and the
five-layer intelligence stack choose FAST/SMART/VISION/CODING/PLANNING/REVIEW/
SUMMARY/LOCAL routes. `ObservedProvider` adds circuit breakers and telemetry.

These calls originate on the desktop using the user's own configured credentials.
There is **no server-side AI gateway** in `server/app.py`. No AI request currently
passes through a cloud plan/quota policy. Never place owner AI credentials in the
desktop to simulate SaaS. Existing BYOK/local operation must be retained as a
clearly identified personal mode, separate from future owner-funded service.

## 5. Existing desktop UI

Tk `JarvisDesktop` has chat, sidebars, quick actions and the ARC HUD. Extensions
install chat workspace, voice, background/tray, account and command-center views.
`AgentCommandCenter` has missions, health, intelligence, capabilities, observability,
security, self-development and data tabs. The requested Home/Chat/Memory/Vision/
Browser/Computer/Files/Coding/Missions/Automation/History/Settings/Subscription
navigation and context-aware workspace are not implemented as specified.

The `RUN CODE TESTS` handler already calls `_run_tool_async`. It is therefore
incorrect to diagnose a synchronous test subprocess on the Tk thread in this
baseline. The worker has no exception-to-completion path and calls Tk `after`
from the worker. A pre-dispatch permission/audit exception can leave `busy=True`.
Other UI helpers also call Tk from workers. Native wake abort can additionally
block a UI-owned stop/recovery path. These are separate failure modes.

## 6. Existing server and deployment

FastAPI factory `server.app:create_app` exposes auth, `/me`, billing and weather
endpoints; bearer authentication, origin checks, size limits, request-rate records
and no-store headers are present. SQLite WAL supports a single host; this is not
a distributed production gateway. Network/password work is generally outside
SQLite write transactions. `server.worker` retries the durable billing inbox.
`server.backup` and `deploy/` provide backup and service/reverse-proxy templates.

Host/domain/TLS, production database operations, SMTP, merchant/provider accounts,
monitoring/alert destinations and real Windows hardware are not supplied by this
repository. Templates and health endpoints are not proof of a live deployment.

## 7. Fresh baseline test evidence

Executed in this session on Linux, Python 3.12.14, from the exact baseline:

| Suite | Run | Passed | Skipped | Failed |
|---|---:|---:|---:|---:|
| `python -m unittest discover -s tests -v` | 453 | 452 | 1 (Windows DPAPI) | 0 |
| `python -m unittest discover -s tests_server -v` | 30 | 30 | 0 | 0 |

Dependencies were loaded from existing isolated desktop/service package
directories using `PYTHONPATH`; the old venv executable links were unavailable.
No dependency pin was changed. Baseline suite durations were 5.639s and 5.887s.

- Real local SQLite, hashing, file, Git, migration, HTTP TestClient and state-machine
  tests exist. Server tests use fake payment/mail/weather providers: no live charge
  or delivery was tested.
- UIA/OCR, microphone, speech and provider tests use fixtures/mocks. They do not
  demonstrate Windows accessibility, audible output or physical reconnection.
- Self-development tests explicitly inject a trusted fixture runner. The product
  tester still fails closed with `EXECUTION_ISOLATION_UNAVAILABLE`.
- CI defines Linux 3.11–3.14, server, Windows regression and Windows packaging
  jobs. Historical CI for main does not verify a new development commit.

## 8. P0 and release blockers

| ID | Finding | Evidence / impact | Required disposition |
|---|---|---|---|
| P0-UI | Worker exceptions can leave desktop busy; worker invokes Tk | `gui.py:_run_tool_async`; no exception completion | Queue results and errors; main-thread polling; duplicate/close recovery tests |
| P0-EXEC | No reviewed project-code OS sandbox | `coding_tools.py:run_unit_tests`, `self_development/tester.py:_run` intentionally deny | Build/review a real isolation adapter; do not enable host Python with only a timeout |
| P0-VOICE | Wake stop calls native `stream.abort()` synchronously | `wake_service.py:stop`; GUI `BackgroundController._stop_listener_only` calls it | Bounded abort ownership; do not multiply workers if native driver wedges |
| P0-ASR | Cancellation/timeout can leave ASR worker alive while later calls start more | `microphone.py:_bounded_transcribe` starts a thread per call | Single ownership until real worker exit; process isolation/recovery still needed |
| P0-SEMANTIC | Semantic actions absent from normal schemas/dispatch; readiness overstates integration | `tools.py` vs `computer_use/`; UIA dependency alone reports AVAILABLE | Correct readiness; add full identity/freshness/sensitive-field guards before exposure |
| P0-EVIDENCE | Semantic type checks a substring already present, with no before/after proof | `action_engine.py:semantic_type` | Require changed observed value and focus; retain UNKNOWN when evidence is insufficient |
| P0-REPLAY | Verification exception replaces already-drained tool events | `orchestrator.py:_execute_step` exception handler | Preserve collected evidence; prevent retry/replan of uncertain side effects |
| P0-BOOL | Explicit verification accepts truthy non-booleans | `verification.py:_explicit_verification` | Require literal `True`; invalid contracts cannot certify success |
| P0-SAAS | Owner-funded AI authentication/entitlement/quota enforcement missing | Server endpoint/schema inventory | Design and implement only after reliability/security gates |
| P0-WINDOWS | Physical acceptance/installer/update/rollback not evidenced | No target machine in this session | Real device and clean-machine evidence; HOLD release |

Existing benchmark truthiness/scenario-count issues from PR #24 also require
regressions before benchmark evidence is allowed to certify improvement.

## 9. Files expected to change

First reliability increment: `jarvis/gui.py`, `ui_command_center.py`, a shared
Tk event-queue helper, `wake_service.py`, `microphone.py`, `agent/orchestrator.py`,
`agent/verification.py`, `computer_use/action_engine.py`, capability status,
targeted new tests and audit/release documentation. Changes must follow failing
regressions and keep existing APIs unless a security defect requires narrowing.

Later SaaS increments extend `server/store.py`, `app.py`, `billing.py`,
`recovery.py`, `worker.py`, `subscription_client.py`, provider factory/adapters,
account/UI modules and deployment configuration with explicit migrations.
New entitlement, usage-ledger and gateway modules belong inside the existing
server package. They must not import desktop config, private files or local tools.

## 10. Files and invariants to preserve

Do not broadly replace `core.py`/`core_v7.py`, memory stores, capability/security
policy, audit integrity, browser target checks, secret/DPAPI handling, effect
ledger, backup/migrations, updater checkpoints, self-development policy/sandbox/
release/rollback, startup child dispatch or public-release HOLD controls.
Targeted security fixes are permitted with regressions; protection does not mean
known defects must be retained. Do not change credentials, merchant settings,
live databases, user memory, dependency pins or main merely to satisfy a test.

## 11. V8 implementation plan

1. Freeze baseline evidence; create `v8-saas-smart-jarvis` from the exact SHA.
2. Repair worker error completion/Tk queue ownership and voice stop/ASR worker
   bounds. Prove event-loop heartbeats during delayed jobs and recovery on errors.
   Preserve execution denial until a reviewed OS sandbox exists.
3. Fix evidence loss/unsafe replay and false verification; strengthen semantic
   identity, target freshness and sensitive-field handling before integration.
   Validate on Windows; retain partial/experimental status until then.
4. Extend the existing account service with migrations for plan definitions,
   features, model policies, user roles, sessions/devices and suspension/deletion.
   ADMIN is a privileged role, never a checkout-selectable entitlement.
5. Add a server-only gateway using adapters over normalized provider turns.
   Authenticate, recheck subscription, authorize feature/model, reserve budget,
   classify task, route, call provider, finalize usage and return sanitized output.
   Retain permission/audit/verification for local desktop actions.
6. Use transactional request IDs and quota reservations (daily/monthly tokens,
   cost and concurrent leases), bounded input/output, fail-closed unknown usage,
   server model/pricing catalogs and circuit breakers. Test concurrency, retries,
   cancellation, crashed requests and quota exhaustion before owner-funded calls.
7. Extend signed billing reconciliation to plan-price mapping, invoices, all
   requested lifecycle transitions and downgrade policy. Test live merchant
   sandbox events and email delivery before any real sale.
8. Introduce the context-aware Tk shell incrementally over working views. Show
   real server usage/subscription and real task state. Add Home, memory controls,
   notifications and admin views backed by authorized APIs; no fake statistics.
9. Extend memory/mission/browser/coding/automation only over verified primitives.
   A recurring workflow needs persisted trigger/condition/action state, recovery,
   permissions and cancellation; `automation.py` is currently a desktop primitive
   module, not such a scheduler.
10. Finish isolation/security tests, Windows repeated wake/Bluetooth/sleep/tray
    tests, clean install/upgrade/rollback/uninstall data checks, deployed backend
    load/backup/recovery/monitoring and an evidence-based final release audit.

## 12. Risk assessment and feature matrix

GREEN means the stated, scoped behavior is implemented, integrated, tested and
verified. YELLOW is partial; RED is a blocker; GREY missing; BLUE experimental.
There are deliberately no blanket green product claims based on mocked tests.

| Feature | Status | Implemented / integrated | Test evidence | Verification and security limit | Plan access |
|---|---|---|---|---|---|
| Local profiles/history isolation | YELLOW | Yes / desktop | user_profiles, Windows launch tests | Separate app profiles are not an OS security boundary; DPAPI hardware pending | Local |
| Online registration/login/reset | YELLOW | Yes / API + account UI | 30 baseline service tests | Real SMTP, deployment, sessions UI/deletion missing | Free |
| Billing checkout/webhook recovery | YELLOW | Yes / API + worker + UI | Fake provider, real DB/HTTP/signature tests | Live Stripe lifecycle and production unavailable | Free/Pro weather |
| Configurable Free/Pro/Advanced/Admin | GREY | No / no | None | Existing binary entitlement is not sufficient | Missing |
| AI feature/model entitlement engine | GREY | No / no | None | Must enforce on server; UI/local config is not authority | Missing |
| Server AI gateway and cost quotas | GREY | No / no | None | No owner-key exposure permitted | Missing |
| Desktop provider/router/circuit breaker | YELLOW | Yes / core | Routing/fault fixtures | Live provider authentication/recovery unverified | BYOK/local |
| RUN CODE TESTS | RED | UI exists / execution denied | Isolation denial tests | Missing OS sandbox; no live project-run stream/cancel evidence | Permission-gated |
| Semantic computer use | RED | Engine exists / ordinary runtime absent | Fake UIA/OCR | Identity/freshness/password protection and Windows evidence missing | Local experimental |
| Voice/background wake | RED | Yes / desktop | Synthetic audio, mocked devices | Blocking native abort/worker ownership; hardware soak pending | Local |
| Memory lifecycle | YELLOW | Yes / core + selected UI | SQLite lifecycle/secret tests | Full inspect/edit/delete Memory Center still required | Local |
| Mission recovery/evidence | RED | Yes / core + UI | State/persistence tests | Post-dispatch verification exception can lose replay evidence | Local |
| Browser public reading/security | YELLOW | Yes / tools | Injection/private-target/DNS tests | Complete multi-step browser agent/live outcomes pending | Local |
| Coding agent/self-development | BLUE | Partial / command center | Trusted fixture runner; Git policy tests | Product code execution denied; no autonomous production deployment | Operator-controlled |
| Smart Home/context-aware UI | GREY | Requested redesign absent | None | Existing desktop usable; no fabricated weather or progress | Missing |
| Owner admin dashboard | GREY | No / no | None | Roles/backend authorization required before UI | Missing |
| Trigger/condition automation V3 | GREY | Primitives/reminders only | Existing primitives | Durable workflow scheduler not implemented | Missing |
| Telemetry/health/readiness | YELLOW | Yes / desktop and service health | SQLite/health tests | No deployed monitoring; cost observation is not billing enforcement | Local |
| Installer/update/rollback | BLUE | Scripts/guards exist | CI definitions, fixture/package tests | Clean Windows acceptance, signing, real upgrade rollback pending | Operator |

Duplication/reachability review: core/memory inheritance and UI installer wrappers
are intentional compatibility layers; do not delete them on filename similarity.
Legacy `core_v7.run_mission` is superseded for the public subclass. Semantic action
engine and `CodingAgentV2` are exercised directly by tests but not exposed as full
normal runtime workflows. `BrowserAgent` and benchmark helpers also need call-path
review before advertising autonomous product capabilities. Dynamic exports and
entrypoints mean a missing static import is not proof that a module is dead.

Documentation drift: README's Computer Use CI check marks do not establish runtime
integration or physical verification; SECURITY's main/V6 branch table and ROADMAP
promotion wording are stale. Update claims to match evidence; keep release HOLD.

## Phase reports

Audit/baseline: inspected architecture, schemas, execution paths, deployment files
and test boundaries; changed this report only. Added no runtime code or tests in
the audit phase. Baseline passed as above. Security impact: none. Regression risk:
none from the report. Next: dedicated development branch and failing P0 regressions.

Subsequent implementation/test outcomes are recorded in `V8-P0-VALIDATION.md`.
