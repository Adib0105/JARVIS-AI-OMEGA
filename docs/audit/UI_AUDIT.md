# UI Audit — V8

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

Source-level UI audit only: Tk dark/cyan ARC desktop, secondary command center, account/voice/settings windows and tray extension. No fresh Windows screenshot or accessibility inspection was performed. Existing hosted package smoke is historical evidence of launch/composer visibility, not visual acceptance of the requested unified graphite/red command center.

See [reproduction evidence](REPRODUCTIONS.md), [the full register](FINDINGS.md) and [execution sequence](V8_FRONTIER_EXECUTION_PLAN.md).

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

### V8-017

- **Severity:** P2
- **Location:** jarvis/background_ui.py; jarvis/gui.py; jarvis/windows_integration.py; jarvis/fast_commands.py
- **Problem:** Global activation hotkey, workspace profile manager and a durable unified notification/approval queue are not implemented.
- **Root Cause:** Existing Ctrl+Space bindings belong to Tk voice controls; background actions are individual desktop shortcuts.
- **Impact:** The requested always-ready workflow cannot be invoked and followed consistently from another foreground application.
- **Recommended Fix:** Register an opt-in OS hotkey with conflict reporting; add workspace definitions using verified app/file primitives and persistent notifications.
- **Implementation Status:** MISSING as unified services
- **Test Required:** Hotkey while Chrome is focused, conflict/unregister, profile restore opt-in, partial app launch and notification recovery.
- **Verification Method:** Activation works outside Tk and every workspace step reports its actual outcome without stealing focus unexpectedly.

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
