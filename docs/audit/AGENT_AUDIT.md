# Agent Audit — V8

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

Planning/execution/verification/recovery already exist. The first implementation priority is evidence integrity: duplicate dispatch after verifier failure, false local completion, malformed explicit verification and false benchmark evidence. Only then expand autonomous action surfaces. Model narrative is not a postcondition.

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

### V8-002

- **Severity:** P1
- **Location:** jarvis/agent/verification.py:53-67
- **Problem:** The literal string "false" in an explicit verified field is accepted as verified=true; evidence can be null.
- **Root Cause:** bool(value) coerces arbitrary truthy data instead of validating a boolean evidence contract.
- **Impact:** Malformed adapter output can promote an unobserved action to verified. This is a contract defect; no external attacker-to-handler exploit was demonstrated.
- **Recommended Fix:** Require strict booleans, compatible status and typed per-tool evidence; reject malformed/unsupported verification rather than falling back to success.
- **Implementation Status:** OPEN — REPRODUCED
- **Test Required:** False/string/numeric/null/missing flags, empty evidence, model-output status on side effects and valid readback adapters.
- **Verification Method:** Only a registered adapter with exact postcondition evidence may report VERIFIED.

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

### V8-004

- **Severity:** P1
- **Location:** jarvis/evaluation/benchmark.py:83-99
- **Problem:** run_case marks a returned {success: false} object as a successful benchmark result.
- **Root Cause:** The runner applies bool(value) to arbitrary results instead of a strict scenario outcome schema.
- **Impact:** Failed or ambiguous scenarios can inflate benchmark and self-improvement evidence.
- **Recommended Fix:** Accept explicit boolean or a validated typed result only; distinguish blocked/unverified/failed and reject unsupported return types.
- **Implementation Status:** OPEN — REPRODUCED
- **Test Required:** False dictionaries, nonempty failure strings, malformed tuples, exceptions, valid booleans and typed verified outcomes.
- **Verification Method:** No truthy container/string can count as pass; reports retain expected/actual/evidence and reason.

### V8-005

- **Severity:** P2
- **Location:** jarvis/evaluation/benchmark.py:137-162; jarvis/self_development/benchmark.py:59-72
- **Problem:** Adding a benchmark scenario with identical accuracy/latency is reported as successful_improvement=true.
- **Root Cause:** scenario_count is treated as a higher-is-better quality metric, and before/after cohorts are not checked for matching cases.
- **Impact:** A changed/easier test set can appear to prove improved capability and feed improvement decisions.
- **Recommended Fix:** Compare identical versioned scenario cohorts; keep coverage separate from quality; require applicable matched quality metrics and no regression.
- **Implementation Status:** OPEN — REPRODUCED
- **Test Required:** Added/removed/renamed scenarios, category drift, duplicate IDs, same-cohort regressions and genuine same-cohort improvement.
- **Verification Method:** Coverage-only changes never certify improvement; incomparable cohorts produce an explicit inconclusive result.

### V8-006

- **Severity:** P1
- **Location:** jarvis/computer_use/action_engine.py:141-211
- **Problem:** semantic_type reports VERIFIED when typing does nothing and the requested substring already existed in the control.
- **Root Cause:** There is no pre-action value comparison or declared set/append postcondition; containment in the final value suffices.
- **Impact:** The standalone semantic adapter can misreport an action. It is not currently wired as a normal agent tool, limiting present exposure.
- **Recommended Fix:** Specify typing semantics, capture fresh pre/post state, bind control/window identity, and require exact expected state; deny secret/unknown targets.
- **Implementation Status:** OPEN — REPRODUCED in a fake UI backend; no real desktop action
- **Test Required:** No-op driver with old matching text, wrong focus, unchanged/partial value, Unicode, replacement, stale control and password fields.
- **Verification Method:** No-op fixture is not verified; actual exact value transition is observed on a real Windows fixture before promotion.

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

### V8-010

- **Severity:** P1
- **Location:** jarvis/computer_use/browser.py; jarvis/computer_use/browser_security.py; jarvis/web_tools.py; jarvis/youtube_player.py
- **Problem:** The general browser agent is public read/search plus default-browser opening, without a coherent tab/frame/form session API.
- **Root Cause:** The specialized visible YouTube driver does not supply general browser forms, downloads, uploads or session semantics.
- **Impact:** Google Form filling/submission, navigation continuation and duplicate-submit prevention are not implemented end to end.
- **Recommended Fix:** Add an explicit session-backed driver under existing URL/injection policy, bind origin/field/session, separate fill from submit and reconcile submission IDs after timeout.
- **Implementation Status:** PARTIAL — public reader/search present; general forms MISSING
- **Test Required:** Local form fixture with redirects, frames, duplicate buttons, password/OTP fields, timeout-after-submit, download hash and upload review.
- **Verification Method:** Filled values and final confirmation are independently observed; ambiguous submission is never automatically replayed.

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
