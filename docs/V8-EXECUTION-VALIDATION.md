# V8 P0.1 continuation — isolated test execution

2026-10-06. Parent: `e7835275c653170cd43b16cc51796b3eb4791494`.
Branch: `v8-saas-smart-jarvis`; draft PR #25. **Release HOLD; full V8 incomplete.**

## Changes and reasons

- Shared Docker Linux isolation adapter in `jarvis/code_execution.py`, bounded
  process/pipe transport in `jarvis/process_runner.py`. No host execution fallback,
  mounts, network, secret environment forwarding or mutable image selection.
- Connect `coding_tools.py` and `self_development/tester.py` to that adapter.
  Preserve existing tool approval, allowed roots, effect ledger and audit.
- Extend `ui_tasks.py` for bounded progress and owner-thread permission calls;
  `gui.py` adds live output/Cancel Tests; `runtime_guard.py` uses the same approval
  queue. Cancellation does not release busy ownership before cleanup finishes.
- `tools.py` propagates failed checks accurately; `agent/verification.py` requires
  a strict successful result and confirmed cleanup. `agent/event_safety.py` masks
  stdout/stderr in persisted mission evidence.
- `tests/test_v8_execution.py`: 23 new policy, subprocess and Tcl regressions.
  Update three existing shutdown tests in `test_runtime_polish.py` to exercise
  the new owner-polled approval queue while retaining denial/recovery assertions.
- `tests_sandbox/test_docker_execution.py` and the new CI job execute real
  container security/lifecycle cases; the existing public-release HOLD remains.
- Setup/threat boundary: `docs/CODE-EXECUTION.md`, `.env.example`; current status
  reflected in README, CHANGELOG, ROADMAP and capability reporting.

## Local evidence

Linux Python 3.12.14, existing pinned desktop dependencies, ResourceWarning as error:
**494 desktop tests: 493 passed, one Windows DPAPI skip, zero failures (7.047s).**
The 23 new tests include real process floods, timeout/cancellation, inherited child
pipes and real headless Tcl live output/approval/cancellation. Docker control-plane
responses are fixtures in that local suite; they are not real isolation evidence.

Initial integration run found three legacy approval-queue test failures/errors:
the shutdown fixture had no new queue, and the closing guard needed an early
denial. The guard and fixtures were corrected; no test was deleted or disabled.
No local Docker engine is available. Bubblewrap also failed its namespace probe.
Real Docker and remaining platform/service check results will be recorded after CI.

## Security impact and regression risk

Execution is opt-in and fails closed before spawning if the immutable image/runtime
configuration is missing. A dedicated trusted Docker engine/image/kernel remains
part of the boundary; this is not a hardware VM guarantee. Text-only snapshots
intentionally omit private/runtime/build folders and unsupported fixtures. The
new queue changes approval scheduling without changing approval policy.

Timeout/cancel/flood/error paths forcibly remove the container and require cleanup
confirmation. Unknown cleanup blocks new execution until recovery. A PID-1
watchdog limits work after an app connection loss. Sudden host/app crashes can
leave stopped container records; crash-persistent garbage collection remains open.
Windows Docker Desktop and rendered GUI acceptance have not been performed here.
General arbitrary builds/shell execution are not exposed.

## Remaining work and next step

Complete real-daemon CI evidence; then continue native voice process recovery and
semantic application/window identity, freshness and sensitive-field enforcement.
Physical Windows microphone/Bluetooth/sleep/tray/installer evidence still requires
a target machine. SaaS gateway, configurable plans, entitlements, quotas, extended
accounts/billing, admin and UX phases remain in the audited implementation order.
This report updates P0.1; it does not mark any full V8 release gate green.

Rollback is a normal Git revert of this increment; no database schema/user data
changes are involved. The existing fail-closed host execution behavior remains the
fallback before and after rollback.
