# Reliability Audit — V8

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

Existing retry limits, intent persistence, SQLite closing connections, ownership checks, wake readiness, updater checkpoints and billing reconciliation are present. A green baseline does not close the new duplicate-action reproduction. Persisted mission history is distinct from a restart-resumable scheduler. Close-to-tray is distinct from a process-independent host.

See [reproduction evidence](REPRODUCTIONS.md), [the full register](FINDINGS.md) and [execution sequence](V8_FRONTIER_EXECUTION_PLAN.md).

### V8-001

- **Severity:** P1
- **Location:** jarvis/memory.py:253-260; jarvis/tools.py:283-295; jarvis/agent/verification.py:128-132; jarvis/agent/event_safety.py
- **Problem:** Completing a nonexistent todo returns completed=false, but the production registry/verifier reports VERIFIED.
- **Root Cause:** The dispatcher treats a returned payload as success; the default verification path accepts ok=true. Sanitized nested output also omits completed.
- **Impact:** A failed local state change can become a completed mission and positive learning/evaluation evidence.
- **Recommended Fix:** Use typed local-write outcomes, preserve a privacy-safe outcome field, read back the requested row/state, and fail closed for side effects without a postcondition adapter.
- **Implementation Status:** OPEN — REPRODUCED
- **Test Required:** Missing, already-completed and newly-completed todo through RecordingToolRegistry and VerificationEngine; local-write contract inventory.
- **Verification Method:** A missing ID never becomes VERIFIED; successful completion is bound to the requested ID and observed done state.

### V8-003

- **Severity:** P1
- **Location:** jarvis/agent/orchestrator.py:254-309; jarvis/agent/effects.py:98-111
- **Problem:** A verification timeout after a successful side effect causes the same mission step to execute again. One requested todo became two.
- **Root Cause:** The exception handler drains events a second time and replaces already-collected step.tool_events with an empty list. Retry safety then sees no effect. ACKNOWLEDGED intents do not block this replay.
- **Impact:** Duplicate side effects are possible following verification/persistence/progress failures after dispatch.
- **Recommended Fix:** Preserve attempt evidence through every exception; block replay and automatic replan of uncertain effects until reconciliation. Bind durable operation identity to a logical mission step.
- **Implementation Status:** OPEN — REPRODUCED
- **Test Required:** Inject verifier, persistence and progress failure after a real local write; repeat after process restart; retain safe read-only retries.
- **Verification Method:** Exactly one row/action is created, evidence survives, and the mission remains failed/unverified until reconciled.

### V8-007

- **Severity:** P1
- **Location:** desktop_app.py:61-93; jarvis/background_ui.py; jarvis/wake_service.py:60-174
- **Problem:** Background wake and tray behavior are owned by the desktop Python process.
- **Root Cause:** Close-to-tray hides Tk while the same process stays alive; there is no independent agent host with authenticated IPC.
- **Impact:** Minimization can work, but UI-process crash/exit ends the runtime. A persistent autonomous service is not implemented.
- **Recommended Fix:** Add a least-privilege per-user agent host and authenticated local IPC; make Tk a reconnecting client. Keep interactive desktop automation in the logged-in user session.
- **Implementation Status:** PARTIAL — tray/wake implemented; independent host MISSING
- **Test Required:** UI detach/exit/crash, host crash, relaunch, unauthorized IPC client, replayed IPC command and profile switching.
- **Verification Method:** Host survives UI loss, rejects forged clients and reloads durable work without blindly replaying effects.

### V8-008

- **Severity:** P1
- **Location:** jarvis/agent/mission.py; jarvis/agent/mission_store.py; jarvis/agent/orchestrator.py:114-151,452-587; jarvis/agent/effects.py
- **Problem:** Persisted missions do not provide a durable priority/dependency queue or restart-resume execution; resume only addresses an in-memory control.
- **Root Cause:** One current mission/profile ownership slot serializes work; there is no dequeue/lease/checkpoint-reconciliation service.
- **Impact:** Requested concurrent long missions and safe recovery after restart are unavailable.
- **Recommended Fix:** Extend existing storage with queue states, task dependencies, owner lease/heartbeat and checkpoints; reconcile external effects before resume; add resource/account/browser/file locks.
- **Implementation Status:** PARTIAL — persistence exists; durable background scheduling MISSING
- **Test Required:** Crash at intent/dispatch/acknowledgement/checkpoint boundaries; competing workers; locked resources; expired deadline.
- **Verification Method:** Independent jobs can progress; conflicting jobs serialize; restarted uncertain work requires reconciliation.

### V8-011

- **Severity:** P1
- **Location:** jarvis/microphone.py:48-131; jarvis/wake_service.py:87-174; jarvis/speech_worker.py
- **Problem:** Microphone capture and abort use daemon threads; a native driver that hangs can retain microphone ownership.
- **Root Cause:** Python-level timeouts return control but cannot reliably terminate a stuck native capture call. Existing speech worker isolation is for output, not capture.
- **Impact:** Wake/command input can remain unavailable until device/app restart; real barge-in/echo resilience is unverified.
- **Recommended Fix:** Move native capture into a supervised subprocess with bounded IPC, readiness/heartbeat and device-generation tokens; preserve visible microphone controls.
- **Implementation Status:** PARTIAL — bounded threads/recovery exist
- **Test Required:** Hung read/abort, unplug/replug, Bluetooth switch, permission denial, sleep/resume, wake while speaking and frozen child startup.
- **Verification Method:** Capture child can be terminated/restarted without killing the UI or leaking ownership; physical audio trials pass declared thresholds.

### V8-012

- **Severity:** P1
- **Location:** jarvis/agent/budget.py; jarvis/agent/tool_runtime.py; jarvis/agent/orchestrator.py; jarvis/background_ui.py:154-157
- **Problem:** Cancellation is cooperative between operations; not all synchronous tools/providers can be interrupted, and there is no unified global emergency stop.
- **Root Cause:** Cancellation tokens are not implemented by every adapter; tray menu only exposes open, microphone pause and full exit.
- **Impact:** Stop can arrive after dispatch or while work blocks; the UI cannot truthfully promise immediate cancellation or undo.
- **Recommended Fix:** Add cancellable bounded read adapters and central stop propagation; journal dispatched effects and report observed state instead of pretending rollback.
- **Implementation Status:** PARTIAL
- **Test Required:** Cancel during permission wait, network read, parse, browser action and after acknowledged external success; tray/hotkey stop.
- **Verification Method:** No new effect starts after acknowledged stop; already-dispatched work is reconciled and cancellation latency is measured.

### V8-013

- **Severity:** P1
- **Location:** jarvis/coding_tools.py:46-59
- **Problem:** Approved file writes replace the destination directly and name backups with only second precision.
- **Root Cause:** Path.write_text truncates before completion; successive writes in one second can select the same backup filename.
- **Impact:** Interrupted writes can damage a file and repeated edits can overwrite the earliest rollback copy.
- **Recommended Fix:** Use exclusive unique backups, write/fsync a temporary file on the same filesystem, atomically replace and verify hashes; preserve path/symlink policy.
- **Implementation Status:** OPEN — source-confirmed; fault injection pending
- **Test Required:** Same-second repeated writes, disk-full/permission errors, process kill before replace, symlink swap and backup restore.
- **Verification Method:** Original or complete new bytes always survive a failed write; every backup is unique and restores the corresponding prior version.

### V8-018

- **Severity:** P2
- **Location:** jarvis/automation.py; jarvis/local_files.py; jarvis/agent/effects.py; jarvis/background_ui.py
- **Problem:** There is no approved-event automation engine with durable deduplication or semantic FileSystemAgent workflow.
- **Root Cause:** automation.py provides immediate input/browser operations rather than a persistent scheduler/file watcher.
- **Impact:** Natural-language rules such as organizing new PDFs, safe bulk move/rename and Wi-Fi connect/verify are unavailable.
- **Recommended Fix:** Introduce event records, stable event/operation keys, debounce/loop prevention and scoped trust policies; add file/app/Wi-Fi adapters incrementally.
- **Implementation Status:** MISSING as end-to-end workflows; local read/app primitives exist
- **Test Required:** Duplicate file events, self-trigger loops, locked file, ambiguous references, network drop and retry after uncertain effect.
- **Verification Method:** One authorized event produces at most one reconciled effect and ambiguous files/network targets remain untouched.

### V8-021

- **Severity:** P2
- **Location:** desktop_app.py:69-92; jarvis/ui_command_center.py:438-475; jarvis/gui.py; jarvis/background_ui.py
- **Problem:** UI composition is extension/monkeypatch driven; several command-center refresh exceptions are silently discarded.
- **Root Cause:** Independent UI extensions accumulate state/callback ownership and prefer silent best-effort refresh.
- **Impact:** Health/security panels can be stale without an error indicator; the requested unified dark command center is not present.
- **Recommended Fix:** Expose a canonical state/event interface, surface per-panel degraded/stale status with redacted logs, then consolidate layout and restrained graphite/red styling.
- **Implementation Status:** PARTIAL — source review only; no fresh visual desktop assessment
- **Test Required:** Injected refresh failure, close/reopen, tray restore, keyboard access, resize/DPI and responsiveness screenshots.
- **Verification Method:** Each failed panel shows stale/degraded state; actual Windows layout and keyboard operation are verified after integration.

### V8-022

- **Severity:** P1
- **Location:** .github/workflows/ci.yml; .github/branch-protection.main.json; scripts/sign_windows_release.ps1; scripts/apply-update.ps1
- **Problem:** Live main branch protection is disabled; no rulesets were returned. Signing is an operational script, not evidence of signed production artifacts.
- **Root Cause:** A protection template does not apply server policy, and source presence cannot certify certificate/provenance or real-device rollback.
- **Impact:** Green CI alone cannot enforce review or establish a production-safe release chain.
- **Recommended Fix:** Apply reviewed required checks/reviews, verify signing/provenance on exact artifacts and perform clean-machine upgrade/rollback drills; keep publication disabled.
- **Implementation Status:** OPEN — main protected=false and rulesets=[] observed on 2026-10-04; release intentionally BLOCKED
- **Test Required:** Live protection readback, signed artifact verification, corrupt download, interrupted/disk-full update and user-data restore.
- **Verification Method:** Server policy is enforced and exact signed artifact hashes have complete install/rollback/acceptance evidence.

### V8-023

- **Severity:** P1
- **Location:** tests/evaluation/; tests/test_background_wake.py; tests/test_voice_reliability.py; .github/workflows/ci.yml; server/README.md
- **Problem:** The requested 100+ realistic corpus, 720-scenario OMEGA Gauntlet and 450-scenario Background Gauntlet have not been executed; real hardware/provider/merchant acceptance is absent.
- **Root Cause:** Existing 453 desktop and 30 service tests primarily validate deterministic software behavior and fixtures; they are not 483 real-world missions.
- **Impact:** No justified broad autonomy success rate, voice reliability claim or production-ready label exists.
- **Recommended Fix:** Version scenario manifests and adapters, collect blocked/unverified outcomes honestly, bind physical/provider results to commit/artifact/device and define thresholds before running.
- **Implementation Status:** BLOCKED for production acceptance; automated baseline PASS
- **Test Required:** 100 wake trials per declared condition, eight-hour soak, real mic/speaker/Bluetooth/DPI/browser, live test provider auth/recovery and Stripe/SMTP test deployment.
- **Verification Method:** Reports record expected/actual/verification/calls/cost/failure/recovery; false-success rate is measured from independent ground truth.
