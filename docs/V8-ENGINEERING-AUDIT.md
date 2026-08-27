# JARVIS AI OMEGA V8 Engineering Audit

## Audit scope and evidence boundary

This document is a current-state engineering audit, not a production-readiness certificate.

- Repository: `Adib0105/JARVIS-AI-OMEGA`
- Branch audited: `v7-development`
- Audit base commit: `64173ba15dcdf9a2ff589cd1ea7e4915d317bc2e`
- Product version authority at audit time: `jarvis.version.APP_VERSION` (`8.0.0-rc1`)
- Exact-base CI evidence observed during the audit: Linux regression on Python 3.11/3.12/3.13/3.14 PASS; Windows regression on Python 3.14.7 PASS; EXE/installer build was still in progress when the audit snapshot was written.
- Physical Windows device behavior, audible TTS, microphone capture, real browser/UI interaction, live provider inference, upgrade/repair behavior, and operator UX are **not** promoted to verified status by this document.

The audit follows the rule: configuration, importability, dependency presence, or an accepted operating-system input event are not equivalent to real-world verification.

## Executive finding

The repository is no longer a prototype. It already has meaningful foundations for persisted missions, capability policy, tamper-evident audit logging, memory lifecycle management, provider deadlines, computer-use verification, evaluation, controlled self-development, reproducible dependencies, Windows packaging and isolated clean-install validation.

The remaining work is primarily **semantic unification, truthful state reporting, lifecycle/cancellation hardening, provider health integration, adversarial boundary hardening, release upgrade validation, static quality gates, and real Windows evidence**. A full rewrite would add risk without solving these gaps.

The most important current blockers are:

1. **P0 — self-development protection boundary is incomplete.** The enforced generated-change policy protects `jarvis/security/`, `policies.py` and `rollback.py`, but does not currently make the sandbox boundary, release engine or Git safety implementation immutable. Model prompt instructions are not a security boundary.
2. **P0 — capability/health state can overstate verification.** Capability refresh stamps `last_verified` with the current time even when no live verification occurred, and several capabilities become `AVAILABLE`/health `PASS` from configuration or dependency presence alone.
3. **P1 — no unified `OperationResult` contract.** Tools, browser, missions and provider paths use a mixture of strings, dictionaries and subsystem-specific result objects.
4. **P1 — cancellation is not end-to-end mission-owned.** Mission cancellation has a control event, while provider requests have a separate request budget. The inspected orchestration path does not bind them into one cancellation propagation chain.
5. **P1 — provider resilience components are not yet one operational subsystem.** A circuit breaker implementation exists, but the inspected provider factory/runtime path does not wire a provider registry/health/circuit/fallback policy together.
6. **P1 — browser public-target validation is incomplete against DNS/redirect edge cases.** Initial URL checks are good, but the normal read path does not prove DNS resolution/final redirect target remains public.
7. **P1 — release validation covers fresh install but not the full upgrade/repair matrix.** The current installer does not remove the historical installed `JARVIS-OMEGA-V7.exe`, so an upgrade can leave an obsolete executable behind.
8. **P1 — packaged application EXE version-resource evidence is incomplete.** Installer metadata is canonical, but `build_windows.ps1` does not currently pass a PyInstaller version resource for `JARVIS-OMEGA.exe`.
9. **P2 — configuration is centralized but not self-describing.** The frozen settings object has defaults and startup validation, but there is no authoritative schema carrying description, allowed values, sensitivity and validation metadata for every setting.
10. **P2 — CI lacks explicit static-quality/coverage gates and separate security/evaluation reporting.** Full regression is strong, but there is no current `pyproject.toml` or consolidated lint/type/format/coverage policy.

## Current architecture map

```text
Desktop entry
  desktop_app.py
    -> runtime/composed desktop UI
    -> jarvis.core.JarvisOmega

Public core
  jarvis/core.py
    -> subclasses jarvis/core_v7.py compatibility provider core
    -> providers/*
    -> agent/* persisted mission orchestration
    -> agent/tool_runtime.py audited tool execution
    -> security/* capability permission + audit + secret controls
    -> memory_v7.py + memory_lifecycle.py + retrieval.py
    -> capability_registry.py
    -> observability/*
    -> evaluation/*
    -> skills/*
    -> self_development/* (lazy in normal runtime)

Provider layer
  providers/factory.py
    -> OpenRouterProvider | OpenAIProvider
    -> optional LocalProvider fallback
  providers/deadline.py
  providers/observed.py
  providers/router.py
  providers/circuit_breaker.py (implemented component; integration incomplete)

Computer/browser layer
  computer_use/windows_ui.py
  computer_use/targets.py
  computer_use/visual_fallback.py
  computer_use/action_engine.py
  computer_use/browser.py
  computer_use/browser_security.py

Persistence
  SQLite-backed memory, mission, audit, observability, evaluation,
  proposal, skill, backup and related tables

Controlled self-development
  observe/evaluate/gap -> proposal -> Git worktree sandbox
  -> bounded code generation -> tests/security/evaluation/diff review
  -> approval -> controlled fast-forward release -> post-tests -> Git revert rollback

Windows release
  build_windows.ps1 -> PyInstaller one-folder app
  build_installer.ps1 -> Inno Setup
  GitHub Actions -> Windows regression -> package -> isolated fresh install/uninstall
```

## Domain-boundary assessment

The target package structure should be approached incrementally. Existing cohesive packages should be kept and strengthened. Flat modules should move only when the move reduces a real dependency or testing problem.

| Target domain | Current state | Audit decision |
|---|---|---|
| `agent/` | Existing cohesive package | Keep; harden lifecycle/cancellation/telemetry. |
| `providers/` | Existing cohesive package | Keep; integrate registry/health/circuit/fallback policy. |
| `security/` | Existing cohesive package | Keep as protected core. |
| `computer_use/` | Existing cohesive package | Keep; expand Windows integration/failure tests. |
| `browser/` | Browser currently inside `computer_use/` + flat `web_tools.py` | Do not move merely for naming. First define secure network/browser boundary; migrate only if dependency clarity improves. |
| `tools/` | Tool implementations/runtime are split across flat modules and `agent/tool_runtime.py` | Introduce a package only during OperationResult/tool-contract migration, preserving legacy imports. |
| `memory/` | `memory.py`, `memory_v7.py`, `memory_lifecycle.py`, `retrieval.py` remain flat | Cohesion is high enough to justify a future compatibility package, but not before lifecycle/result contracts stabilize. |
| `documents/` | `documents.py` + memory index/retrieval | Current pipeline is incomplete as a full RAG lifecycle. Package migration should accompany index/citation/update/delete contracts, not precede them. |
| `storage/` | Existing package | Keep. |
| `observability/` | Existing package | Keep; expand aggregate metrics and lifecycle ownership metrics. |
| `evaluation/` | Existing package | Keep; expand deterministic scenario suite. |
| `health/` | Implemented under `observability/health.py` | Do not duplicate. Either retain location or move with compatibility import after status semantics are corrected. |
| `self_development/` | Existing package | Keep; strengthen immutable boundary first. |
| `skills/` | Existing package | Keep. |
| `release/` | Controlled release lives under self-development; Windows packaging is top-level scripts/installer | Do not create a second release engine. Separate application self-modification release from Windows product release in interfaces/docs. |
| `ui/` | Mixed flat GUI/UI modules plus composed classes | Gradual migration only after functional behavior is stable. |
| `voice/` | Flat voice/microphone modules + UI composition | Gradual package migration may help lifecycle ownership later; not a Phase-0 rewrite. |
| `config/` | `config.py`, `config_validation.py`, version/product paths | First create typed metadata/schema; package split later if it adds clarity. |
| `common/` | Small shared contracts/errors/logging currently flat | A compact common package is justified when unified result/error contracts are introduced. |

## Detailed gap register

| CURRENT | PROBLEM | RISK | RECOMMENDATION | PRIORITY | DEPENDENCIES | TEST COVERAGE |
|---|---|---|---|---|---|---|
| `CapabilityRegistry` has operational states and runtime-derived records. | Missing `NOT_VERIFIED`; `last_verified` is set to `now()` on every refresh even without verification; several `AVAILABLE` states are based on config/import presence. | Operator/model can receive a false impression that a device/service was recently verified. | Separate operational state from evidence level; add `NOT_VERIFIED`, `test_status`, `last_verified_at=None` unless qualifying evidence exists, `failure_rate`, `degraded_reason`; ingest measured rates from persisted evidence rather than inventing them. | P0 | diagnostics, evaluation, observability, UI | Existing capability tests; add truth-table tests for configured-but-unverified provider/mic/voice/computer-use. |
| `JarvisHealthSystem` checks Python, provider config, DB, filesystem, voice, mic, Computer Use, Git, sandbox, etc. | Health enum lacks `NOT_VERIFIED`; provider/local AI/voice/mic/Computer Use can PASS when only configured/importable/backend-present. | Health dashboard can convert unknown/live-unverified state into a healthy claim. | Add `NOT_VERIFIED`; reserve PASS for the level actually exercised; show configured/installed details separately. | P0 | CapabilityRegistry, diagnostics | Existing observability/health tests; add explicit no-live-evidence cases. |
| Self-development uses Git worktrees, bounded file/line limits and an enforced path policy. | Enforced immutable prefixes omit `sandbox.py`, `release.py`, `git_manager.py` and other production activation/boundary controls. Model prompts say not to edit protected code, but prompts are not enforcement. | Generated code could weaken its own sandbox/release/Git safety boundary if approved by an insufficient review path. | Expand immutable protected control set; reject symlink/junction/reparse escapes and protected-target aliases; add adversarial regression tests. | P0 | self-development builder/policy, Windows path behavior | Existing self-development tests; new direct attack tests required. |
| `jarvis.core.JarvisOmega` layers V8-era services over `core_v7.JarvisOmega`. | Two-core inheritance remains and `core_v7` still has duplicate model-selection/error/fallback logic plus stale V6 compatibility commentary. | Drift risk and developer confusion; fixes can land in the wrong core. | Keep compatibility API, but progressively move shared provider/request lifecycle into explicit services; make `core_v7` a thin compatibility facade only after regression proof. | P1 | provider/result/error contracts | Mission architecture/runtime composition tests exist; add facade parity tests during migration. |
| Mission state machine persists states, retries, recovery, replans, pause/cancel and final verification. | Mission control cancellation and provider `RequestBudget` cancellation are separate. Inspected step execution calls `core.chat()` without binding mission control to provider cancellation. Cancelled work may continue in daemonized provider thread until transport/deadline termination. | User cancellation may return UI control while external/provider work continues longer than expected. | Introduce cancellation token/lifecycle context propagated plan -> provider -> tool -> browser/computer-use/TTS; classify `USER_CANCELLED`; add cancellation-at-each-stage tests. | P1 | request lifecycle, tools, browser, voice | Inference lifecycle tests exist; targeted mission cancellation propagation coverage required. |
| RetryManager + verification-aware side-effect retry blocking exist. | Error taxonomy is narrower than system domains; cancellation currently can become `UNKNOWN_ERROR`; browser/storage/security/sandbox/release failures lack stable categories. | Recovery policy and telemetry can become inconsistent or unsafe. | Introduce backward-compatible standardized error taxonomy and mapping adapters; base retry policy on normalized category + idempotence. | P1 | unified OperationResult, observability | Existing error/failure tests; expand failure-injection matrix. |
| Tools have permission/audit contracts; browser/computer-use return evidence-rich dictionaries; missions have `VerificationResult`. | No standard `OperationResult`; tool runtime protocol returns `str`; result semantics are duplicated. | UI/orchestrator/evaluation can interpret the same outcome differently, especially PARTIAL/UNVERIFIED. | Add a common `OperationResult` with VERIFIED/PARTIAL/FAILED/UNVERIFIED and compatibility serialization; migrate boundaries incrementally, starting tool runtime/browser/computer-use. | P1 | common contracts, error taxonomy | New contract unit/property tests + adapter regression tests. |
| Provider package has OpenAI/OpenRouter/local providers, deadlines, model router, observed wrapper and a circuit breaker implementation. | No authoritative `ProviderRegistry`/`ProviderHealth`; inspected factory does not wire `ProviderCircuitBreaker`; fallback policy lives in core rather than one provider policy service. | Repeated provider failures can bypass intended circuit logic; health/fallback telemetry can drift. | Integrate provider registry + per-provider health/circuit state + fallback policy; emit circuit/fallback telemetry; never infer cost. | P1 | observability, errors, settings | Circuit breaker unit tests may exist; add integration tests proving factory/runtime actually uses it. |
| Observability persists redacted events/resources and provider usage/cost/latency. | Aggregate coverage is provider-heavy; no single metrics surface for mission retry/replan/verification rates, tool PARTIAL/UNVERIFIED, queue/background workers, self-development release/rollback counts. | Operators cannot diagnose reliability trends or resource lifecycle regressions from one source. | Extend `ObservabilityManager` aggregate/time-window queries from existing persisted evidence; do not duplicate event stores. | P1 | OperationResult, mission telemetry, service lifecycle | Existing observability tests; add aggregate correctness tests. |
| Evaluation engine measures persisted mission/tool/recovery/replan/browser/computer-use evidence and returns `None` for unsupported metrics. | Deterministic scenario suite is small (`tests/evaluation` currently contains benchmark/security/self-improvement files only); several quality metrics explicitly remain unmeasured. | Self-improvement decisions can be under-informed despite green regressions. | Add deterministic scenario catalog for chat/tools/browser/computer-use/memory/documents/recovery; persist scenario IDs/evidence/version; define acceptance thresholds. | P1 | unified results, fixtures/fakes, readiness model | Existing evaluation tests are a foundation; substantial expansion required. |
| Browser security blocks invalid schemes, credentials, localhost/private literal IPs and scans prompt injection. | Normal public read path does not enable DNS validation; final redirect destination is not independently proven public by inspected wrapper. | DNS rebinding/public-name-to-private resolution or redirect edge cases may cross local network boundary. | Resolve and validate all target addresses before request where feasible; use a fetch layer capable of redirect-hop/final-target validation or reject opaque fetches for sensitive modes. | P1 | web fetch implementation, DNS-safe tests | Adversarial browser tests exist; add DNS/private-resolution and redirect tests with deterministic mocks. |
| Memory has working/episodic/semantic/procedural layers, source/confidence/time, reinforcement, superseding, contradiction detection and stale decay. | Lifecycle state is split across `active`, status and relation/event tables; `MemoryRecord` does not expose a content/provenance hash; explicit archive/delete semantics are not yet one authoritative API. | Data lifecycle behavior is harder to reason about and evaluate. | Define one backward-compatible memory lifecycle facade; include provenance/hash metadata and explicit archive/delete/update operations; preserve existing tables. | P2 | storage migrations, retrieval | Strong V7/V7.5 memory tests exist; add lifecycle transition/property tests. |
| Document reader hashes content/extracted text and captures file metadata; memory index dedupes unchanged sources. | No complete authoritative INGEST->HASH->EXTRACT->CHUNK->INDEX->RETRIEVE->CITE->UPDATE->DELETE lifecycle object; parser/version/index-version and citation correctness benchmarks are incomplete. | Stale indexes and provenance/citation quality can be difficult to prove. | Add document registry/lifecycle on top of existing extractor/index, with stable document IDs, parser/index versions, stale detection, deletion and citation references. | P1 | memory/retrieval, migrations, evaluation | Extraction tests exist; add update/delete/stale/citation/retrieval benchmark tests. |
| Audit log has sanitized argument hashes and a tamper-evident chained integrity table; `verify_integrity()` detects row/hash/link damage. | Audit record and integrity-event schema are split and lack an explicit actor field in the main audit row. | Forensics can be less expressive about who initiated an action. | Preserve chain design; add actor/origin metadata in an additive migration if evidence needs it; retain explicit “tamper-evident, not tamper-proof” documentation. | P2 | migration, tool runtime | Existing audit integrity/security tests are meaningful. |
| Configuration is centralized in frozen `Settings`; startup validation exists; product data paths are separated. | Settings are dense one-line declarations in places and have no authoritative metadata for description/allowed values/security sensitivity; some invalid numeric env values silently fall back to defaults. | Misconfiguration can be hidden and UI/docs can drift from actual settings. | Add typed config spec metadata and parse findings; distinguish missing/defaulted/invalid; redact sensitive fields by schema. Preserve current environment variable compatibility. | P2 | diagnostics, UI/settings, docs | Configuration tests exist; add invalid-env/redaction/schema completeness tests. |
| Windows build uses canonical app version, exact dependencies, stable `JARVIS-OMEGA.exe`, package healthchecks and secret bundle validation. | PyInstaller command does not provide an application EXE version resource derived from `APP_VERSION`. | File properties can lack canonical product/file version even though installer metadata is correct. | Generate PyInstaller version resource from `jarvis.version` during build and test the built EXE file version on Windows. | P1 | build script, version module | Version consistency tests exist; add Windows binary metadata assertion. |
| Inno Setup installer uses canonical version and stable executable; isolated CI validates fresh install/uninstall and user-data preservation. | No upgrade/repair/reinstall matrix; historical installed `JARVIS-OMEGA-V7.exe` is not explicitly removed during upgrade. | Upgrade can leave stale executable; fresh-install CI would not detect it. | Add `[InstallDelete]` migration for obsolete product binary and an upgrade CI job seeded with a legacy install fixture/package; add repair/reinstall validation. | P1 | installer fixture/artifact strategy | Fresh install/uninstall coverage exists; upgrade coverage missing. |
| CI compiles, runs full unittest regressions on Linux/Windows, packages, scans bundle, performs isolated install/uninstall and post-package regression. | No explicit lint/format/type/dead-import/complexity/coverage gate; no `pyproject.toml`; security/evaluation results are not surfaced as distinct required jobs. | Maintainability defects and declining critical-path coverage can pass until runtime tests catch them. | Add minimal actionable static checks and coverage thresholds focused on critical paths; split security/evaluation gates where it improves failure diagnosis. | P2 | tool selection and dependency pinning | Existing functional regression gate is strong. |
| Branch CI is active. | `v7-development` is currently unprotected and required status checks are not enforced by branch protection. | A direct push can bypass review/required-check policy. | Enable GitHub branch protection/ruleset with required CI checks and review policy. This is repository administration, not application code. | P1 | GitHub repository settings | Not testable in application unit tests; verify settings externally. |
| Current commits are accepted by GitHub. | Audited head commit is unsigned. Release signing/AuthentiCode provenance is not established. | Operator cannot cryptographically validate publisher provenance of source commit/Windows binary. | Define signing policy: signed release tag/commit plus Windows Authenticode in protected release workflow using secured credentials. | P2 | signing certificate/secrets, protected CI | Requires release-infrastructure validation. |
| GUI uses composition for voice and Command Center extensions; startup class mutation was removed. | Base GUI and several historical file/table/test names still contain V6/V7/V7.5 labels; some are legitimate history, some are compatibility debt. | Developers may confuse product version with historical architecture generation. | Maintain a version-occurrence inventory classified CURRENT/HISTORICAL/REGRESSION_TEST/OBSOLETE; remove only accidental live labels. | P2 | compatibility docs/tests | Existing version consistency/composition tests help. |
| Voice output has worker/runtime tests and packaged TTS worker healthcheck. | Physical audible output, microphone lifecycle and device switching remain live-device concerns; capability/health status currently overstates dependency presence. | False confidence and possible worker/audio-resource leaks on real hardware. | Correct status semantics first; then add lifecycle ownership + repeated start/stop tests and manual exact-build device evidence. | P1 | health, service lifecycle, Windows E2E | Software tests exist; physical device validation remains NOT_VERIFIED. |
| `production_readiness.json` does not exist yet. | No objective machine-readable release gate currently combines architecture/security/reliability/testing/evaluation/observability/recovery/Windows/packaging/docs. | “Ready” can become a narrative judgement. | Implement a readiness evaluator after status/result/evaluation semantics stabilize; weakest critical gate must cap overall readiness. | P1 | all earlier evidence systems | New deterministic readiness tests required. |

## Existing strengths that should be preserved

- Canonical application version source and reproducible dependency constraints.
- Provider-neutral interfaces and hard request deadlines.
- Persisted mission state machine with verification, bounded recovery and replanning.
- Side-effect-aware retry prevention.
- Canonical capability permission gate with unknown tools failing closed.
- Secret redaction and persistence blocking.
- Root/path traversal and symlink/junction file-security regression coverage.
- UIA-first computer-use architecture with ambiguity rejection and post-action evidence semantics.
- Browser content explicitly treated as untrusted data with prompt-injection scanning.
- Tamper-evident audit chaining with an integrity verifier.
- Layered memory, contradiction detection, superseding and stale confidence decay.
- Evidence-based evaluation that leaves unsupported metrics unmeasured instead of fabricating values.
- Controlled Git worktree self-development, bounded code generation, reviewed file staging, fast-forward-only production activation and history-preserving Git revert rollback.
- Production self-modification disabled by default.
- Windows build, secret-exclusion scan, installer generation, isolated clean install/uninstall and post-packaging regression pipeline.
- Documentation already states that CI does not prove physical-device/live-service behavior.

## Duplicate and drift map

### Core

`jarvis/core.py` is the production public core; `jarvis/core_v7.py` is a compatibility provider core. The previous duplicated mission loop has been removed, but provider/model/fallback/error behavior still exists at both layers. Treat this as migration debt, not two equal production cores.

### Permission

The legacy permission API is a compatibility adapter around the capability-based permission authority. Do not recreate a second rule table.

### Status terminology

There are currently three related concepts that must not be collapsed carelessly:

1. capability operational state (`AVAILABLE`, `DEGRADED`, etc.);
2. diagnostic evidence level (`INSTALLED`, `CONFIGURED`, `DEVICE_VERIFIED`, etc.);
3. operation verification result (`VERIFIED`, `PARTIAL`, `FAILED`, `UNVERIFIED`).

The fix should define how they relate, not create a fourth vocabulary.

### Provider resilience

Timeout/deadline, observation, routing and circuit-breaking components exist, but they are not yet one authoritative provider runtime service.

### Persistence

Subsystems intentionally share SQLite but own different tables. This is not inherently duplicate DB access; the common SQLite connector/migration discipline should be retained. Consolidate only cross-cutting lifecycle/transaction rules, not all repositories into a god-store.

## Target migration sequence

### Phase 1 — baseline stability

- Freeze evidence to exact commit/run.
- Finish exact-head package/install/post-package CI.
- Add upgrade cleanup before calling packaging migration complete.
- Add regression tests before P0 security/status changes.

### Phase 2 — unified semantics

- Introduce common `OperationResult` and operation verification enum.
- Normalize error taxonomy with compatibility aliases/adapters.
- Define capability-state vs diagnostic-evidence semantics.

### Phase 3 — capability registry + health

- Add `NOT_VERIFIED` and evidence timestamps that are never fabricated.
- Feed measured rates from observability/evaluation.
- Health PASS must mean the check it describes actually ran successfully.

### Phase 4 — observability

- Add mission/tool/system/self-development aggregate queries and lifecycle ownership metrics.
- Preserve current redaction/provider-reported-cost-only rule.

### Phase 5 — security

- Expand immutable self-development controls immediately.
- Add DNS/redirect public-target defenses.
- Produce formal threat model and security-center evidence mapping.

### Phase 6 — mission/recovery/cancellation

- One cancellation token/context across planning/provider/tool/browser/computer-use/voice/self-development.
- Add crash/orphan recovery policy and terminal-state sweep.

### Phase 7 — memory/doc/browser/computer-use verification

- Add authoritative document lifecycle/citation metadata and benchmark fixtures.
- Strengthen lifecycle APIs without rewriting existing storage.
- Expand Windows failure-mode tests where deterministic automation is possible.

### Phase 8 — evaluation

- Deterministic scenario catalog with before/after comparison and acceptance thresholds.

### Phase 9–11 — self-development/release

- Harden protected boundaries and sandbox path attacks first.
- Separate APPROVED, RELEASED/DEPLOYED and VERIFIED evidence states.
- Keep history-preserving rollback.

### Phase 12 — Windows release

- EXE version resource, upgrade/repair/reinstall matrix, signing/provenance policy, exact-build manual device/live-provider validation.

### Phase 13–14 — UI/docs/cleanup

- Command Center consumes the same status/result/metrics contracts.
- Classify and clean legacy labels only after compatibility proof.
- Generate production-readiness JSON from evidence, never from static marketing claims.

## Release blockers at audit base

The audit base must **not** be called 10/10 or fully production-ready while any of these remain:

- self-development can enforceably modify its sandbox/release/Git control implementation;
- capability/health timestamps/states can imply verification that did not occur;
- no end-to-end cancellation ownership across mission/provider/tool services;
- no unified operation result semantics;
- browser DNS/final-target validation gap remains;
- exact-build upgrade/repair/reinstall validation is absent;
- packaged EXE version metadata is not proven canonical;
- exact-head package/install/post-package CI has not completed successfully;
- branch protection/signing policy is absent;
- required physical Windows GUI/device/live-provider E2E evidence remains unverified.

## Audit rule for subsequent changes

For every implementation phase:

```text
AUDIT -> DESIGN -> IMPLEMENT -> TARGETED TEST -> FAILURE/ADVERSARIAL TEST
-> FULL REGRESSION -> SECURITY REGRESSION -> DOCUMENT -> EXACT-COMMIT EVIDENCE
```

Do not carry PASS evidence from an older commit into a newer commit. Do not change a status to positive merely because code exists or imports successfully.