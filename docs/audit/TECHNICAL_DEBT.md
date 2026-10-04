# Technical Debt — V8

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

The compatibility core/memory layers are intentional migration seams, not proven dead code. Preserve call-site compatibility and add a deprecation map before removal. Broad exception handling must be classified by recovery behavior; blanket deletion can cause GUI crashes.

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

### V8-009

- **Severity:** P1
- **Location:** jarvis/tools.py:58-151,226-279; jarvis/computer_use/action_engine.py; jarvis/computer_use/windows_ui.py; jarvis/computer_use/targets.py
- **Problem:** Semantic UIA/OCR components and security profiles exist, but semantic tools are absent from ordinary schemas/handlers; target freshness and password metadata are incomplete.
- **Root Cause:** Standalone adapters were intentionally not promoted to the canonical tool path; low-level coordinate/keyboard tools remain separate.
- **Impact:** The requested observe-locate-act-verify desktop agent is not end-to-end available; premature wiring could target the wrong or sensitive field.
- **Recommended Fix:** Introduce typed observation/action contracts with stable process/window/control identity, stale-target rejection and secret-field handling, then wire through one policy/audit/verification path.
- **Implementation Status:** BLOCKED for verified semantic autonomy
- **Test Required:** Schema-handler-contract parity; stale/ambiguous target, secure field, focus theft, DPI and multimonitor Windows fixture tests.
- **Verification Method:** Every exposed action uses a fresh authorized target and independent requested postcondition; no coordinate fallback guesses.

### V8-014

- **Severity:** P2
- **Location:** jarvis/capability_registry.py:195-249
- **Problem:** Computer Use can be AVAILABLE from UIA initialization although semantic tools are not wired; Windows Power Pack status relies on OS/config without an action probe.
- **Root Cause:** Dependency availability is conflated with end-to-end runtime readiness.
- **Impact:** Planner/UI can overpromise capabilities that are missing, stale or unverified.
- **Recommended Fix:** Separate installed, integrated and verified readiness; bind tool inventory, last successful probe, expiry and failure evidence to registry health.
- **Implementation Status:** OPEN — source-confirmed
- **Test Required:** Missing handler, dependency present but unusable, disconnected device, expired probe and provider auth failure.
- **Verification Method:** A module import or OS flag cannot alone make the requested workflow AVAILABLE.

### V8-015

- **Severity:** P2
- **Location:** jarvis/agent/budget.py:17-24; jarvis/agent/orchestrator.py:476; jarvis/config.py
- **Problem:** Shared budgets exist, but default request/mission limits are embedded in code and no durable long-mission budget/priority contract exists.
- **Root Cause:** ExecutionBudget is instantiated with hardcoded values; missions use a 180-second budget and a finite ownership window.
- **Impact:** The requested configurable hours-long workflow cannot be represented or safely accounted for across restart.
- **Recommended Fix:** Validate budget configuration centrally and persist elapsed/call/token accounting, deadline and ownership renewal; avoid one unbounded exemption.
- **Implementation Status:** PARTIAL
- **Test Required:** Budget exhaustion in plan/retry/tool/review, invalid config, restart accounting, pause/expiry and bounded ownership renewal.
- **Verification Method:** Every path shares enforced limits and restart never resets consumed budgets.

### V8-016

- **Severity:** P2
- **Location:** jarvis/core_v7.py:276-307; jarvis/agent/mission.py; jarvis/agent/orchestrator.py:342-381
- **Problem:** Plans are lists of strings with permissive parsing; explicit assumptions, dependencies, constraints, risk and verification/fallback plans are not persisted.
- **Root Cause:** Compatibility planning predates the V8 operational schema; several requested mission states/metadata fields are absent.
- **Impact:** Malformed or incomplete plans are hard to validate, inspect or resume safely.
- **Recommended Fix:** Add a versioned typed plan/mission schema with compatible migration and strict validation; persist only concise operational reasoning.
- **Implementation Status:** PARTIAL
- **Test Required:** Malformed JSON, unknown capabilities, dependency cycles, impossible constraints, round-trip and legacy migration.
- **Verification Method:** Invalid plans fail before dispatch and every executable step has a declared capability and verification rule.

### V8-019

- **Severity:** P2
- **Location:** jarvis/memory_v7.py; jarvis/memory_lifecycle.py; jarvis/document_index.py; jarvis/retrieval.py; jarvis/documents.py
- **Problem:** Memory/RAG foundations exist, but complete document deletion/reindex lifecycle, page/section citations and the full requested provenance/owner/expiry UX are not demonstrated.
- **Root Cause:** Current stores and content hashes focus on indexing/retrieval; no broad relevance/citation benchmark closes the end-to-end quality gap.
- **Impact:** Stale source answers, weak citations and incorrect remembered context can survive green parser/unit tests.
- **Recommended Fix:** Define source lifecycle and memory ownership/consent schema, preserve page/section metadata, implement coordinated deletion, and benchmark labelled retrieval/citation tasks.
- **Implementation Status:** PARTIAL
- **Test Required:** Changed/deleted/duplicate document, contradiction/supersession, profile separation, expiry/export/reset, table/OCR extraction and labelled retrieval.
- **Verification Method:** Answers cite current identifiable sources; deleted/expired data is excluded from every retrieval path.

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

### V8-024

- **Severity:** P2
- **Location:** docs/KNOWN-LIMITATIONS.md; README.md; .github/workflows/ci.yml; docs/V7.9-AUDIT-REPAIRS.md
- **Problem:** Some limitations text says budgets, durable intents, rollback and cross-process locks are absent despite V7.9 code; README readiness labels overstate integration. Current CI lacks explicit formatting/lint/type-check gates.
- **Root Cause:** Documentation and pipeline descriptions have drifted across release generations.
- **Impact:** Users and reviewers cannot reliably distinguish implemented foundations, known defects and missing acceptance.
- **Recommended Fix:** Make one evidence-bound status register authoritative, reconcile README/limitations without erasing history, and introduce scoped maintainability/type gates incrementally.
- **Implementation Status:** OPEN — source/workflow-confirmed
- **Test Required:** Documentation links and capability-contract parity, actual CI job inventory, scoped lint/type baseline and release-gate consistency.
- **Verification Method:** Each advertised capability maps to an integrated path and current evidence; every stated required CI gate actually runs.
