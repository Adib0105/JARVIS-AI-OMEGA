# Final hardening audit — release blocked

Date: 2026-09-21. This is a partial hardening change, not completion of the production-readiness mission. No finding is CLOSED. The requested stop/report rule applies to the missing verified execution-isolation boundary; unsafe host execution has been disabled.

## Branch selection

- main: `4e4431ba5f331b1e080cbca69d974b1a5087ed14`, September 13; retains recent speech/tray/installer/Defender fixes.
- codex/v75-production-hardening: `a4390dc162bfbfbea5033e3aa0fa9e05b98622b2`, August 28; reusable mission CAS and transition logic.
- audit/v8-production-hardening: `1d4d7212a59c8242f585b80eb058e5d528988607`, August 28; reusable pinned HTTP reader and control-plane policy, but divergent product features and absent September fixes.

Safest base: main. No branch merge. Selectively adapted existing mechanisms rather than replacing current main with either older branch.

## Findings

IN PROGRESS means implemented mitigation with incomplete finding-wide evidence. VERIFIED below is limited to the explicitly named Linux invariant; it does not mean CLOSED or Windows verified.

| Finding | Previous state | Change | Regression/evidence | Status and remaining work |
|---|---|---|---|---|
| F01 | Generated tests execute as host user | Both self-development tester and project-test tool fail closed with EXECUTION_ISOLATION_UNAVAILABLE; no approval override | Nine attack categories assert no subprocess launch | IN PROGRESS — disabled execution proven, sandbox not implemented; Windows isolation unavailable |
| F02 | Generated edits can modify control plane | Port immutable control-plane policy; protect security, CI, scripts, installer and selected security tests | Protected-path assertions | IN PROGRESS — full transitive trust-base/bypass review incomplete |
| F03 | Model text and unchanged focus can imply success | No-tool claims and unobserved clicks return UNKNOWN; mission result remains PARTIAL | No-tool/focus regressions; existing desktop and mission suite | IN PROGRESS — all requested stale/conflicting/timeout/postcondition cases not covered |
| F04 | Ordinary reader can reach untrusted destinations | Port numeric-address-pinned sockets; reject mixed/private DNS and validate redirects; preserve TLS hostname verification | Private URL, mixed DNS and redirect tests | IN PROGRESS — real transport/rebinding adversarial integration and total request deadline incomplete |
| F05 | Stale mission writes and unrestricted transitions | Revision CAS, legal transitions, atomic state/event transaction; legacy state names supported | Stale snapshot, event rollback, illegal transition and pause tests | VERIFIED — local SQLite state invariant only; distributed execution belongs to F22 |
| F06 | Updater lacks transactional recovery | Existing integrity/helper controls preserved | Existing updater regressions run | OPEN — staged known-good backup, startup health, rollback and failure-loop protection missing |
| F07 | Semantic browser tools not integrated end to end | Existing permissions preserved; shared URL validation strengthened | Component tests only | OPEN — planner-to-observation path and unsafe navigation/download tests incomplete |
| F08 | Raw secrets can enter history and mission fields | Shared redactor before chat, summaries, mission state/events and structured logs; redact crash stderr | Supplied synthetic secrets absent from tested databases/log output | IN PROGRESS — arbitrary secret formats, all stores/exports/telemetry and historical data not proven |
| F09 | Coding model kind coerced to mission | Preserve requested coding kind | Model-selection regression fails on main, passes here | IN PROGRESS — full intent/edit/test/diff route remains unproven and execution is blocked |
| F10 | Irrelevant candidates always ranked | Require lexical/BM25 evidence or embedding score >= 0.65 | Relevant/unrelated/empty cases | IN PROGRESS — calibrated confidence, explicit NO_RELEVANT_CONTEXT and citation contract incomplete |
| F11 | Legacy migration copies main DB without WAL | SQLite online backup, bounded progress, unique staging, integrity check before replacement | Live WAL connection retains latest committed table; old copy loses table | VERIFIED — migration backup invariant on Linux; continuous-writer/Windows fault matrix incomplete |
| F12 | Project tests treated as harmless/trusted | HIGH risk, side-effecting, removed trusted auto-approval; execution blocked | Trusted-mode denial, retry-risk and project-test denial | IN PROGRESS — requested category taxonomy not implemented |
| F13 | No total mission budget | Existing bounded replans/retries retained | No new total-budget proof | OPEN — wall time/model/tool/token/cost/browser/filesystem global accounting missing |
| F14 | Disabled handlers directly callable | Dispatcher validates enabled schemas and primitive arguments before permission/handler | Disabled web/coding/mail and unknown-name probes | IN PROGRESS — all aliases/direct subsystem routes and deep argument validation incomplete |
| F15 | Automatic release and unprotected main | Disable publication job while blockers remain; add dedicated adversarial and pip-check gates | Workflow diff; existing Windows/package/Defender jobs preserved | IN PROGRESS — remote branch protection/required checks unchanged; hosted gates not yet observed |
| F16 | Dependencies not reproducibly locked | pip check added to Linux/Windows regression jobs | Local pip check passes | OPEN — target-platform lockfiles, vulnerability/license validation missing |
| F17 | Source launcher requires .env | Removed pre-launch .env checks in Windows desktop and terminal batch launchers | Source inspection; no-key desktop package gate | IN PROGRESS — source batch first run needs on-PC validation |
| F18 | Silent exception paths | Inventory inspected, no blanket replacement | No complete classification evidence | OPEN — repository-wide handling rationale and fault-injection coverage incomplete |
| F19 | Unbounded local text read | Regular-file/2 MB checks, bounded read, binary detection, safe decode, Unix no-follow/nonblocking open | Tiny/huge/binary/malformed cases | IN PROGRESS — document/index readers, ancestor races, Windows reparse/device cases and timeouts incomplete |
| F20 | Multiple config writers/sources | Serialize connection save/apply within one process | Existing connection failure/persistence suite passes | IN PROGRESS — no concurrent-update proof, no cross-process CAS or authoritative precedence model |
| F21 | Repair discards evidence context | Repair returns original answer verbatim without another model call | Failure, uncertainty and citation preserved; main regression fails | IN PROGRESS — full final formatting/rendering pipeline evidence audit incomplete |
| F22 | Shared mission ownership races | Reject second mission on one core; release ownership on initial persistence failure; port CAS | Ownership, stale snapshot, event rollback and pause tests | IN PROGRESS — restart resume, cross-process claims and exactly-once side effects not implemented |

## Test evidence

Local environment: Linux, Python 3.12.14, dependencies from main requirements in an isolated virtual environment. Synthetic accounts/keys and mocked external services; no real emails, desktop actions or generated attack payloads executed.

- `python -m compileall -f -q jarvis tests main.py`: exit 0.
- `PYTHONWARNINGS=error::ResourceWarning python -m unittest discover -s tests -v`: **369 tests, 3.139 seconds, OK**.
- `python -m unittest discover -s tests -p test_final_hardening.py -v`: **23 tests, 0.020 seconds, OK** (included in 369, not additional tests).
- `python -m unittest discover -s tests -p test_v7_security.py -v`: **13 tests, 0.006 seconds, OK** (included in 369).
- `python -m pip check`: **No broken requirements found**; not vulnerability scanning or reproducible dependency proof.
- Nine safe regressions replayed against untouched base main: **8 assertion failures and 1 expected missing-table error**. Cases: no-tool verification, unchanged focus, coding routing, unrelated retrieval, response repair, raw chat persistence, WAL backup, disabled dispatcher, file-size cap. WAL case raises `sqlite3.OperationalError: no such table: committed`, demonstrating the lost WAL data. Imports adapted only to available baseline module names; CAS/isolation payload tests were not executed against the unsafe baseline.
- Earlier main baseline: 343 tests passed. Existing test cases were retained; changed expectations reflect UNKNOWN/PARTIAL rather than false verification.

Self-development lifecycle tests explicitly inject a **test-only trusted hello fixture runner**. Those tests still exercise proposal/diff/retry/release bookkeeping, but are **not** sandbox or production generated-code execution proof. Production has no fallback to that runner.

## Windows and release evidence

This editing host is Linux. No Windows executable, installer, microphone, SAPI, wake-word or rollback was executed here. Existing Windows 3.14 regression, package launch, installer/update lifecycle and Defender jobs remain present; adding YAML is not a passing run. Real audio device/permission recovery and broken-update rollback require additional Windows validation even if existing CI passes.

Bubblewrap exists locally, but the namespace probe failed with `loopback: Failed to create NETLINK_ROUTE socket: Operation not permitted`. This proves this runtime cannot supply the tested isolation mechanism, not that Windows isolation is impossible. No reviewed Windows backend is implemented. Generated test operations are unavailable until that boundary is implemented and adversarially validated. Human review must occur outside the autonomous pipeline in a separately reviewed disposable environment; ordinary approval cannot bypass the deny.

Publication is intentionally disabled, not a fake successful security gate. No tests were disabled. Remote branch protection is outside this code change; fetched main metadata reported `protected: false`.

**Release decision: NOT READY FOR RELEASE.** All findings above remain short of finding-wide closure.
