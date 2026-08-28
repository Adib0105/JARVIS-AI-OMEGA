# JARVIS AI OMEGA V7 — Architecture Assessment & Implementation Plan

> **Historical migration plan.** Branch, version and gap statements below describe the original V6→V7 planning baseline, not the current V7.5 implementation. Current evidence lives in [V7.5-PRODUCTION-AUDIT-2026-08-28.md](V7.5-PRODUCTION-AUDIT-2026-08-28.md).

**Branch:** `v7-development`  
**Baseline:** V6 main at `ee0ba1a46caa777590015e2630a42f125d5cb7fd`  
**Target version:** `7.0.0`

## 1. Executive assessment

V6 already has a useful modular surface: Tkinter ARC UI, voice/microphone, image and screen vision, local files, documents, web/news search, Google Workspace, coding/Git helpers, SQLite memory, reminders/todos, permission prompts, CI, and Windows packaging scripts. V7 should preserve those working capabilities.

The main V7 problem is not missing buttons. It is reliability architecture. V6 can call tools and execute missions, but it does not yet have a first-class mission state machine, tool contracts, post-action verification, failure taxonomy/recovery, capability permissions, audit evidence, provider isolation, schema migrations, or strong observability.

V7 therefore evolves V6 rather than rewriting it.

## 2. Current strengths to preserve

- Safe local-root checks and secret-like path blocking.
- Coding writes create backups before replacement.
- No unrestricted shell executor.
- Google account actions are approval-gated.
- SQLite access is protected with a re-entrant lock and short-lived connections.
- Image validation/compression exists before multimodal requests.
- Voice has online neural TTS plus an offline fallback.
- GUI keeps AI work off the Tk main thread for normal chat/vision/mission calls.
- CI currently compiles and runs unit tests on Python 3.11, 3.13 and 3.14.
- V6 main branch remains available as the stable rollback baseline.

## 3. Current weaknesses

### 3.1 Core/provider coupling

`jarvis/core.py` owns OpenAI client construction and contains separate OpenRouter, OpenAI Responses, vision and local-fallback request implementations. That makes provider changes risky and makes testing provider behavior harder.

**V7 direction:** `jarvis/providers/` with a common provider interface and normalized response/tool-call objects. The core/orchestrator should depend on that interface, not SDK-specific response types.

### 3.2 Configuration is parsed but not validated

Environment values are converted directly at import time. Invalid integers/floats can fail before a useful diagnostic is produced. Cross-setting problems (unsupported provider, empty model, invalid timeout, invalid image limits, Google enabled without files) are not represented as structured validation results.

**V7 direction:** safe parsers + `ConfigValidator` returning PASS/WARNING/FAIL findings. Fatal findings block startup with actionable messages; optional feature findings become warnings.

### 3.3 Error handling is string-oriented

V6 has friendly provider errors but no shared failure taxonomy for tools, network operations, missions and providers.

**V7 direction:** typed error categories such as AUTH_ERROR, PERMISSION_ERROR, RATE_LIMIT, TIMEOUT, NETWORK_ERROR, INVALID_INPUT, TOOL_ERROR, RESOURCE_NOT_FOUND, VISION_ERROR, MODEL_ERROR and UNKNOWN_ERROR.

### 3.4 Tool registry mixes four responsibilities

`ToolRegistry` currently defines schemas, initializes tool implementations, checks permission and dispatches execution in one class. Tools do not expose risk level, capabilities, timeout, retry policy, expected side effects or verification strategy.

**V7 direction:** keep the V6 registry working during migration, then add `ToolContract` metadata and move permission/execution/verification into explicit layers.

### 3.5 Permissions are tool-name lists

`PermissionGate` has SAFE and APPROVAL sets. It cannot express policies like FILE_READ=allow, FILE_WRITE=ask, EMAIL_SEND=always ask or session-scoped approval.

**V7 direction:** capability-based policies with risk-aware approval. Existing tool-name behavior remains as a compatibility adapter during migration.

### 3.6 Missions are not durable state machines

V6 Planner → Executor → Reviewer stores only `last_plan` in memory and executes steps in a simple loop. Completed/failed steps, retries, recovery, cancellation and final verification are not persisted.

**V7 direction:** persisted `Mission` + explicit states (IDLE, UNDERSTANDING, PLANNING, WAITING_FOR_PERMISSION, EXECUTING, VERIFYING, RECOVERING, REPLANNING, COMPLETED, FAILED, CANCELLED).

### 3.7 Tool results are not systematically verified

Some implementation functions return useful evidence (for example a created Gmail message ID, calendar event ID, file path, test return code), but the agent does not apply a standard verification contract before claiming success.

**V7 direction:** every important side-effecting tool gets a verification strategy and evidence record.

### 3.8 Memory lacks provenance/confidence layers

V6 stores sessions/messages, summaries, simple facts, notes, knowledge chunks, todos and reminders. Facts do not have confidence/source/last_verified metadata and there is no schema version/migration mechanism.

**V7 direction:** backward-compatible schema migrations, working/episodic/semantic/procedural memory metadata, confidence and source tracking, with current user input always taking priority.

### 3.9 Logging is rotating but not structured

V6 correctly rotates a local log and writes crash reports, but log entries are plain text and there is no audit log, event category, redaction pipeline or mission/tool correlation IDs.

**V7 direction:** JSON structured logs, secret redaction, categories (INFO/WARNING/ERROR/SECURITY/AUDIT/MISSION/TOOL/MODEL), correlation IDs and a separate audit store later in Phase 3.

### 3.10 GUI is directly coupled to the agent instance

The GUI directly starts worker threads and calls `JarvisOmega`. Mission cancellation/pause/resume and a mission timeline do not yet exist.

**V7 direction:** an orchestrator/event interface becomes the GUI boundary. The ARC visual identity stays intact.

### 3.11 CI is useful but incomplete

Current CI runs dependency install, compileall and unittest. It does not yet run lint, type checking, integration/security suites, secret scanning or the V7 evaluation suite.

**V7 direction:** extend CI after the new V7 foundations are in place; do not claim compatibility unless CI actually tests it.

## 4. Proposed V7 architecture

```text
Interface
  GUI / Text / Voice / Vision
        |
Agent
  Orchestrator -> Planner -> Executor -> Reviewer -> Replanner
        |
Context + Intelligence
  Context Manager / Model Router / Provider Abstraction / Retrieval / Memory
        |
Tool Runtime
  Contracts -> Permission -> Execute -> Verify
        |
Recovery
  Classify -> Retry -> Alternative -> Replan
        |
Security + Observability
  Capability Policy / Approval / Audit / Redaction / Metrics / Health
        |
Storage
  SQLite migrations / mission state / memory / audit / metrics
```

## 5. Files to create

### Phase 1

- `jarvis/errors.py`
- `jarvis/config_validation.py`
- `jarvis/providers/__init__.py`
- `jarvis/providers/base.py`
- `jarvis/providers/openrouter_provider.py`
- `jarvis/providers/openai_provider.py`
- `jarvis/providers/local_provider.py`
- `jarvis/providers/factory.py`
- `docs/V7-ARCHITECTURE.md`
- Phase-1 unit tests

### Later phases

- `jarvis/agent/orchestrator.py`
- `jarvis/agent/mission.py`
- `jarvis/agent/context.py`
- `jarvis/recovery/*`
- `jarvis/security/capabilities.py`
- `jarvis/security/audit.py`
- `jarvis/tools/contracts.py`
- `jarvis/observability/*`
- `jarvis/storage/migrations.py`
- `jarvis/self_improvement/*` only after the reliability/security/evaluation foundations exist.

## 6. Files to modify incrementally

- `jarvis/config.py` — safe parsing, V7 version, validation integration.
- `jarvis/core.py` — gradually delegate provider work and later orchestration.
- `jarvis/logging_utils.py` — structured/redacted V7 logs while preserving current public functions.
- `jarvis/tools.py` — later compatibility adapter to tool contracts.
- `jarvis/permissions.py` — later compatibility adapter to capability policies.
- `jarvis/memory.py` — later migrations and memory metadata.
- `jarvis/gui.py`, `jarvis/hud.py`, `jarvis/voice.py` — V7 branding now; mission/health/security UI in later phases.
- CI/build/docs — updated only as features become real and tested.

## 7. Deprecation plan

No working V6 file is deleted in Phase 1. Compatibility functions remain until the V7 replacement is covered by tests. Historical V6 documentation remains historical and is not blindly renamed.

The runtime monkey-patch guard is technical debt. V7 should move identity/quality rules into normal runtime components before deprecating it.

## 8. Migration strategy

1. Keep `main` as the V6 stable baseline.
2. Develop only on `v7-development`.
3. Add V7 foundations without changing the existing SQLite schema in Phase 1.
4. Add explicit schema migrations before any V7 database columns/tables are required.
5. Preserve current public entry points (`main.py`, `desktop_app.py`, `JarvisOmega`) during migration.
6. Add tests before removing compatibility paths.
7. Merge to main only after the V7 quality gate is satisfied.

## 9. Testing strategy

- Unit-test config validation and safe parsing.
- Unit-test error classification.
- Unit-test provider normalization without live API calls.
- Keep every existing V6 regression test running.
- Add integration/mission/security suites in later phases.
- CI remains the source of truth for supported Python versions.

## 10. Security strategy

- Never add arbitrary shell execution, credential harvesting, stealth persistence, hidden recording or silent account actions.
- Provider abstraction must never log API keys or OAuth tokens.
- Structured logging will redact secret-like keys/values.
- Side-effecting actions remain approval-gated during migration.
- Future self-improvement work happens only in isolated development/sandbox areas, with tests, checkpoints and explicit production approval.
- Security policy, permission engine, secret handling, audit boundary and rollback policy are immutable to normal self-improvement logic.

## 11. Phase order

1. Foundation: architecture/provider/config/errors/logging.
2. Agent reliability: mission state/orchestrator/verification/recovery/replanning.
3. Security: capabilities/approval center/audit/security tests.
4. Memory: layered memory/confidence/hybrid retrieval/context.
5. Computer/browser use: semantic targeting + verification.
6. Observability: metrics/health/cost/analytics.
7. Testing/evaluation.
8. Product polish and packaging.
9. Controlled self-improvement sandbox only after the above guardrails are operational.

## 12. Definition of success

V7 does not call an action successful merely because a tool returned without raising an exception. The target flow is:

`Intent -> Permission -> Action -> Verification -> Evidence -> Report`

When evidence is insufficient, V7 reports that it could not verify success instead of claiming “done.”
