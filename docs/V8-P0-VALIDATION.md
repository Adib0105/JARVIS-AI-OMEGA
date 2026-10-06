# V8 first P0 repair increment — validation and remaining gates

Date: 2026-10-06. Branch: `v8-saas-smart-jarvis`.
Baseline: `83b7f34b67c0aca444c1139cd7db700364bc554c`.
**Full V8: incomplete. Release: HOLD.** This increment is reviewable development,
not a production upgrade or an installer release.

## Phase 0 — repository audit

Changed `V8-SAAS-AUDIT.md` with the requested architecture, existing auth/billing/
provider/UI/server inventory, test boundaries, P0 findings, protected areas,
feature matrix, risks and staged implementation plan. Existing SaaS components
must be extended rather than duplicated. No runtime code changed during the audit.
Baseline: 453 desktop tests (452 passed, one Windows DPAPI skip); 30 service tests
passed. Security/regression impact of audit: none.

## Phase 1 — protect mainline

Created local and remote `v8-saas-smart-jarvis` from the exact baseline. Main was
not edited or merged. Runtime versions, dependency pins, server credentials,
payment settings, databases and release/publication guards were not changed.
No production schema migration or rollback of user data is needed for this patch.

## Phase 2 — reproduced faults and repairs

| Change and reason | Files | Tests / evidence | Security and regression impact | Remaining limit |
|---|---|---|---|---|
| Main-thread completion/error queue; duplicate-job exclusion; recover busy/buttons; 65,536-character display limit | `gui.py`, `ui_tasks.py`, `ui_command_center.py` | Real Tcl heartbeats continue while worker is held; errors/SystemExit/thread-start failure restore UI; subsequent job succeeds; late results after closing suppressed; command-center errors delivered on owner thread | No tool permission bypass; one pending job per view. Long-running functions are not falsely reported cancelled | Does not add an OS test runner, stdout/stderr stream, process timeout or cancellation. Other chat/voice/approval UI callbacks still need a wider threading audit |
| Native wake abort moved to one background owner; repeated stops do not spawn more aborts | `wake_service.py` | Simulated blocking native abort does not block stop caller; ten further stops share the same abort; existing wake regressions retained | A wedged native abort blocks listener restart rather than opening a duplicate device | Process-isolated capture/restart and real Bluetooth/sleep/permission-denial soak still needed |
| Retain ASR ownership until actual recognizer exit, discard cancelled late text, handle worker exit | `microphone.py` | Cancelled caller returns while simulated recognizer is held; second recognition rejected; recovery after owner exit; SystemExit releases ownership | Prevents accumulating hidden ASR workers. A permanently stuck recognizer remains unavailable | This is a bounded fail-closed worker, not reliable native-process recovery |
| Preserve drained tool events when later verification fails; prevent uncertain side-effect retry and replan | `agent/orchestrator.py` | Baseline verifier-timeout fixture executed effect nine times; repaired execution is once, zero replans, persisted evidence, FAILED mission | Deliberately more conservative on uncertain effects; read-only retry/replan tests still pass | Not a claim of transactional exactly-once behavior across every crash boundary |
| Strict boolean/known verification contracts and actual todo completion | `agent/verification.py` | String `false`, numeric truthiness and malformed contracts cannot verify; actual SQLite/ToolRegistry nonexistent/already-complete todos fail while a valid update verifies | False success claims reduced; malformed handler contracts now stay UNKNOWN | Other tool outcomes still require individual independent verification contracts |
| Require confirmed focus and a newly observed field value for semantic typing | `computer_use/action_engine.py` | No-op typing with existing requested text no longer verifies; failed focus performs no write; changed value has explicitly scoped evidence | Does not expose semantic actions through the ordinary registry; OCR remains unverified | Complete application/window identity, selector freshness, sensitive-field protection and Windows integration are still missing |
| Mark UIA dependency readiness experimental, not integrated autonomy | `capability_registry.py` | Full existing capability suite passes; source explicitly describes missing runtime/Windows gates | Truthful capability reporting; may lower displayed readiness | Physical dependency detection is not acceptance evidence |
| Strict benchmark success; compare matching scenario sets; exclude sample count from quality improvements | `evaluation/benchmark.py`, `self_development/benchmark.py` | Failed result object, more samples alone, substituted scenarios and truthy success strings rejected; original before/after comparison tests retained | Prevents measured-evidence false positives; no relaxation of release/self-development policy | Benchmark coverage itself remains limited |

Paths in that table are relative to `jarvis/`. All new regressions are in
`tests/test_v8_p0_regressions.py`. README, CHANGELOG, ROADMAP and SECURITY branch
descriptions were updated to state the current development and release boundaries.

### Test results

| Run | Tests | Passed | Skipped | Failed |
|---|---:|---:|---:|---:|
| V7.9 baseline desktop | 453 | 452 | 1 | 0 |
| V7.9 baseline service | 30 | 30 | 0 | 0 |
| First 11 fault regressions, isolated original baseline | 11 | 0 | 0 | 11 cases / 14 failing assertions including subtests |
| Final desktop including 18 new regressions | 471 | 470 | 1 | 0 |
| Final isolated service suite | 30 | 30 | 0 | 0 |

Final desktop: 5.255 seconds; service: 6.017 seconds, Linux Python 3.12.14.
`PYTHONWARNINGS=error::ResourceWarning` was enabled for final suites.
Compileall and `git diff --check` passed. All direct desktop and service package
versions matched their pinned requirements. No pin was changed.

[Machine-readable evidence](evidence/v8-p0-20261006.json) includes suite counts,
log digests, the 18 new case names and source digest. Fault fixtures simulate
native audio/UIA/provider behavior; they are not real hardware evidence. The UI
tests exercise actual Tcl timers and thread ownership without a rendered window.

Reproduce automated checks in separate desktop/service dependency environments:

```bash
python -m unittest discover -s tests -p test_v8_p0_regressions.py -v
python -m unittest discover -s tests -v
python -m unittest discover -s tests_server -v
python -m compileall -f -q jarvis server tests tests_server desktop_app.py main.py
git diff --check
```

Test infrastructure notes: pre-existing venv interpreter links were unavailable;
their installed package directories were used with the current Python runtime.
An initial fault probe terminated because the test interpreter was finalized on
an old worker thread. The test harness was corrected to retain Tcl interpreters
on the main thread, then the clean baseline experiment completed with the failures
shown above. No baseline test was removed or skipped to make the new suite pass.

## Explicit P0 acceptance status

| Requirement | Status after this increment |
|---|---|
| UI result/error recovery and no worker-side Tk calls in the two repaired helpers | Verified by Linux Tcl/thread regressions; Windows rendered acceptance pending |
| RUN CODE TESTS end-to-end subprocess isolation, streaming, timeout, cancellation, process-tree cleanup | **BLOCKED:** no reviewed project-code OS sandbox; existing denial retained |
| UIA semantic integration with identity/freshness/sensitive-field protection | **BLOCKED:** engine corrections only; ordinary dispatch remains unavailable |
| Voice cancellation/reconnect/repeated-wake/idle-soak on Windows | **PARTIAL:** bounded worker defects repaired; native process recovery/hardware evidence open |

Per the requested execution order, the subsequent SaaS feature rollout is not
represented as implemented while these P0 gates remain unresolved. Its concrete
architecture and migration order are recorded in the audit. No fake gateway,
payment provider, plan statistics or admin dashboard has been added.

## All requested release gates

| Gate | State / required evidence |
|---|---|
| 1. RUN CODE TESTS freeze fixed and verified | Partial UI regression evidence; sandbox/execution/Windows gate open |
| 2. Computer-use semantic integration | Open; do not enable prematurely |
| 3. Voice reliability | Open physical/process-recovery acceptance |
| 4. Multi-user isolation | Existing local/account tests pass; full SaaS resources absent |
| 5. Subscription enforcement | Weather only; AI feature/model enforcement absent |
| 6. No owner provider keys in client | No keys added; future AI gateway still needed |
| 7. Billing webhook verification | Existing signature/idempotency tests pass; live lifecycle pending |
| 8. Usage limits | Existing API rate limiting; AI budgets/quotas missing |
| 9. Local premium bypass prevention | Weather server gate tested; V8 premium AI not implemented |
| 10. Browser security | Existing adversarial tests pass; broader/live workflows pending |
| 11. Coding sandbox | Fail-closed guard preserved; reviewed OS runner missing |
| 12. Rollback | Existing fixture tests; physical upgrade/rollback pending |
| 13. Windows physical acceptance | Not performed in this Linux workspace |
| 14. Installer validation | No new installer released; clean-machine acceptance pending |
| 15. Security audit | Scoped source/fault review performed; complete production review remains open |
| 16. Production backend | Not deployed or tested in this session |
| 17. Monitoring operational | Local health/telemetry exists; deployed alerting not verified |
| 18. No known P0 blockers | **Not satisfied — release HOLD** |

## Next validation and rollback

Next implementation work is the reviewed OS-isolated project runner and isolated
native capture lifecycle, followed by semantic identity/sensitive-field integration.
Windows acceptance must include repeated wake/interrupt cycles, unplug/replug,
Bluetooth change, sleep/resume, sign-in/out, tray restore and switching to Chrome.
Record actual attempts, failures, p50/p95 response latency and measured idle soak;
do not populate those statistics from mocks. Then validate clean install, upgrade,
settings/data preservation, interrupted update/rollback and uninstall/reinstall.

The cloud phases additionally need the chosen host/domain, provider configuration,
merchant test credentials and SMTP delivery in their secure server environment.
Those are external validation requirements, not secrets to paste into a report.

Rollback for this branch is a normal Git revert of the reviewed patch. It changes
no persisted schema or user data. Reverting would reintroduce the reproduced P0
defects; retain release HOLD and rerun regression tests before any activation.
