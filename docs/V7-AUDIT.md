# JARVIS AI OMEGA V7 / V7.5 — Repository Audit

**Branch audited:** `v7-development`  
**Audit phase:** Phase 0 — Full Repository Audit  
**Purpose:** Establish the actual current state before any V7.5/self-development work begins.

> Rule for this document: a feature is not marked complete merely because a file exists. “Implemented” means code exists and is visibly integrated; “Verified” additionally requires passing tests/integration evidence. Items that need runtime/manual proof are explicitly marked as such.

---

## 1. Executive summary

The current repository is a real V7 codebase, not a blank scaffold. The strongest implemented foundations are:

- provider abstraction (`jarvis/providers/`)
- V7 mission/orchestrator system (`jarvis/agent/`)
- persisted mission state and verification/recovery infrastructure
- layered V7 memory/context integration
- capability-based security, approval UI, audit logging, secret protection
- Windows semantic computer-use foundation (`jarvis/computer_use/`)
- multimodal/vision/document tooling inherited from V6 and carried into V7
- local/offline OpenAI-compatible provider support foundation
- desktop GUI/ARC HUD/voice controls
- Linux + Windows CI regression coverage

The main V7.5 gaps are not basic chat features. They are the higher-level engineering systems requested in the master plan:

- Capability Registry
- Self-Evaluation Engine
- Capability Gap Detector
- controlled Self-Development/Self-Coding/Self-Debugging pipeline
- sandbox/workspace manager
- self-improvement Git branch manager
- automatic rollback manager
- dedicated skill-generation system
- repeated-workflow learning
- dedicated observability manager + historical metrics
- evaluation benchmark package
- health system/dashboard
- mission dashboard/command center
- security center UI
- database backup/restore UI and integrity workflow
- full V7 installer/version cleanup
- documentation completion

The current branch should therefore be treated as a strong **V7 engineering foundation**, not yet the completed V7.5 self-development system.

---

## 2. Repository structure — observed

### Existing major packages/modules

Observed current structure includes:

```text
jarvis/
  agent/
  computer_use/
  providers/
  security/
  attachments.py
  automation.py
  coding_tools.py
  config.py
  config_validation.py
  core.py
  core_v7.py
  documents.py
  errors.py
  git_tools.py
  gui.py
  hud.py
  local_files.py
  memory.py
  memory_v7.py
  runtime_guard.py
  tools.py
  vision.py
  voice.py
  voice_ui.py
  ...
```

### Major requested packages not currently present as dedicated packages

At the audited tree head, the following master-plan packages are not present as dedicated top-level `jarvis/` packages:

```text
jarvis/evaluation/
jarvis/self_development/
jarvis/skills/
jarvis/observability/
jarvis/storage/
jarvis/browser/
jarvis/ui/
```

This does **not** mean all related functionality is absent. Some responsibilities currently live in older flat modules or other packages, e.g. browser functionality is inside `jarvis/computer_use/browser.py`, UI is primarily `gui.py`/`hud.py`, and SQLite persistence lives in existing memory/mission/audit modules.

---

## 3. Implemented and substantially integrated

### 3.1 Provider abstraction — IMPLEMENTED

Observed:

- `jarvis/providers/base.py`
- `jarvis/providers/factory.py`
- `jarvis/providers/openrouter_provider.py`
- `jarvis/providers/openai_provider.py`
- `jarvis/providers/local_provider.py`

The V7 core uses provider-neutral plumbing rather than keeping all provider logic directly in the GUI.

**Status:** IMPLEMENTED / INTEGRATED  
**Remaining:** routing metrics, richer model-role routing, cost accounting, provider-specific capability reporting, explicit fallback telemetry.

### 3.2 Mission agent foundation — IMPLEMENTED

Observed under `jarvis/agent/`:

- context manager
- mission model
- mission store
- orchestrator
- memory-aware orchestrator wrapper
- recovery logic
- recording tool runtime
- verification engine

The public `JarvisOmega` wrapper exposes mission run, cancel, pause, resume and mission-history methods.

**Status:** IMPLEMENTED / TESTED  
**Remaining:** richer mission dashboard, persisted live command-center telemetry, broader end-to-end evaluation, stronger cancellation of every possible background operation.

### 3.3 Security foundation — IMPLEMENTED

Observed under `jarvis/security/`:

- capability profiles
- capability permission policy
- approval UI
- audit store
- audit viewer
- secret filtering
- Trusted Local Mode for low/medium-risk local actions

The newer runtime replaces the legacy broad permission gate with `CapabilityPermissionGate` and records audit evidence.

**Status:** IMPLEMENTED / TESTED  
**Remaining:** dedicated Security Center dashboard, adversarial test expansion, immutable self-development security-core policy enforcement once self-development exists.

### 3.4 Computer-use foundation — IMPLEMENTED, ACTIVE HARDENING

Observed under `jarvis/computer_use/`:

- `action_engine.py`
- `browser.py`
- `targets.py`
- `windows_ui.py`

This is a real semantic/Windows UI Automation foundation rather than only raw coordinate clicking.

**Status:** IMPLEMENTED / PARTIALLY VERIFIED  
**Remaining:** OCR/visual fallback, stronger dynamic-window recovery, broader post-action verification, browser V2 integration, larger Windows scenario test matrix.

### 3.5 Layered memory/context — IMPLEMENTED

Current V7 public core initializes `V7MemoryStore` and `ContextManager`, and mission reports can be written into episodic V7 memory with confidence/source metadata.

**Status:** IMPLEMENTED / TESTED  
**Remaining:** contradiction detection, stale-memory workflow, confidence decay, reinforcement/superseding, incremental document-index lifecycle, richer retrieval evaluation.

### 3.6 Voice/HUD — IMPLEMENTED

Recent V7 work includes:

- interruptible TTS playback
- stop/play/pause-style controls
- runtime speech speed control
- application shutdown terminating active speech
- ARC HUD states including speaking/listening/thinking/paused

**Status:** IMPLEMENTED / TESTED at helper/regression level  
**Remaining:** longer manual soak tests on Windows audio backends and microphone/wake-word reliability.

### 3.7 CI regression baseline — CURRENTLY GREEN

Current CI includes Linux Python jobs and a Windows Python 3.14 regression job. Recent SQLite handle leaks were fixed and Windows-specific regression coverage was added.

**Status:** VERIFIED at current audited head.  
**Remaining:** Python 3.12 job if supported, integration/evaluation/security benchmark stages, warning-as-failure/resource-leak checks where practical.

---

## 4. Partially implemented systems

### 4.1 Capability Registry — PARTIAL / NOT YET THE REQUESTED REGISTRY

There is already a **security capability profile map** in `jarvis/security/capabilities.py`.

However the requested `CapabilityRegistry` is broader. It must track actual system capability health such as:

- version
- runtime status
- dependencies
- permissions
- risk
- associated tests
- success rate
- last verified time
- implementation path
- AVAILABLE / EXPERIMENTAL / DEGRADED / DISABLED / MISSING / BROKEN

The current security map is useful input, but it is **not yet** the full V7.5 Capability Registry.

### 4.2 Offline/local AI — FOUNDATION EXISTS, COMPLETE OFFLINE DEVELOPMENT LOOP DOES NOT

A local OpenAI-compatible provider exists and configuration supports a local fallback endpoint/model.

Missing for the requested offline-development feature:

- explicit `OFFLINE_DEVELOPMENT_MODE` orchestration
- local development capability checks
- offline self-build pipeline
- offline benchmark/evaluation flow
- UI status explaining why offline development is or is not available

### 4.3 Browser V2 — PARTIAL

A browser abstraction exists inside `jarvis/computer_use/browser.py`.

Still needed:

- dedicated browser-agent boundary or clearer interface
- navigation/read/click/type/extract/verify lifecycle
- stronger webpage prompt-injection handling tests
- domain trust policy integration
- navigation and result verification metrics

### 4.4 Coding agent — PARTIAL

Existing components include `coding_tools.py` and `git_tools.py` with guarded project inspection/write/test/Git read operations.

Still missing from the requested Coding Agent V2/self-coding flow:

- architecture-aware extension-point analysis
- test-first generated change workflow
- isolated sandbox editing
- repair loop with bounded attempts
- automatic regression comparison
- generated diff/proposal object
- approval-controlled merge
- rollback tracking

### 4.5 Documents/RAG — PARTIAL

Document extraction/indexing exists for common formats and memory retrieval exists.

Still needed:

- explicit content hashes for document lifecycle
- duplicate detection across indexes
- incremental updates
- deletion/update handling
- stale index detection
- richer chunk metadata/provenance
- retrieval benchmarks
- OCR/table extraction fallback where appropriate

---

## 5. Missing requested V7.5 systems

The following master-plan systems are not currently present as complete integrated subsystems:

1. `CapabilityRegistry`
2. `SelfEvaluationEngine`
3. `CapabilityGapDetector`
4. `self_development/` package
5. self-improvement proposal model/workflow
6. self-coding engine
7. bounded self-debugging engine
8. self-build sandbox/workspace manager
9. self-improvement Git branch manager
10. automatic rollback subsystem
11. immutable-security-core enforcement specifically for self-development
12. complete offline self-build loop
13. `skills/` package and skill manifest lifecycle
14. repeated workflow learner/proposal generator
15. dedicated `ObservabilityManager`
16. historical cost/resource accounting
17. unified health system
18. Self-Development Dashboard
19. Security Center Dashboard
20. Mission Dashboard / Agent Command Center
21. database export/import/backup/restore UI workflow
22. `tests/evaluation/` benchmark suite
23. self-improvement before-vs-after benchmark system
24. controlled release engine for self-generated improvements

These should not be described in README as implemented until they exist, are wired, tested, and verified.

---

## 6. Broken/inconsistent current-version items

### 6.1 Installer is still V6 — CONFIRMED INCONSISTENCY

The current installer definition is still named:

```text
installer/JARVIS-OMEGA-V6.iss
```

and hard-codes V6 application name/version/executable/output paths.

This is a V7 release-blocker, but not a reason to rewrite the installer before core V7.5 work is stable.

### 6.2 Documentation still contains V6-only material

`docs/V6-USER-GUIDE.md` remains in the V7 branch.

Historical V6 documentation may remain intentionally, but current-version docs must clearly distinguish historical V6 behavior from V7 current behavior.

### 6.3 Test naming contains legacy V6 names

The suite still contains multiple `test_v6_*` files. Some are valid regression tests for preserved V6 functionality, but naming currently mixes historical regression intent with current-version test organization.

Do not delete them simply because they say V6. First classify each as:

- historical regression test to preserve
- current behavior test to rename
- obsolete test only if proven obsolete

---

## 7. Duplicate/overlapping systems and technical debt

### 7.1 Legacy permission gate + V7 capability gate

There are two permission concepts:

- `jarvis/permissions.py` — legacy broad SAFE/APPROVAL gate
- `jarvis/security/policy.py` — V7 capability-based gate

The V7 recording tool runtime replaces the legacy gate at runtime, but the older gate remains because `ToolRegistry` still initializes it.

**Debt:** migrate the base tool registry to a permission interface so V7 does not need runtime replacement/monkey-style substitution.

### 7.2 `core.py` + `core_v7.py`

The public `core.py` is a compatibility wrapper over provider-neutral `core_v7.py` and adds V7 memory/orchestration. This is currently intentional, but the boundary should be documented and eventually simplified once compatibility requirements are clear.

### 7.3 GUI runtime patch layers

V7 behavior is partly added through runtime compatibility/install hooks such as `runtime_guard.py` and `voice_ui.py` over the older GUI class.

This enabled safe incremental upgrades, but long term it increases coupling and makes UI behavior harder to reason about.

**Debt:** during product-polish phase, consolidate into explicit V7 UI components rather than continuing unlimited monkey patching.

### 7.4 Flat modules versus target package boundaries

Requested target architecture calls for dedicated packages (`tools/`, `documents/`, `browser/`, `storage/`, `ui/`). Current code still has several flat modules such as `tools.py`, `documents.py`, `gui.py`, `coding_tools.py`.

Do not reorganize purely for aesthetics. Move code only where it reduces coupling and tests remain green.

---

## 8. Security risks / security notes

### Existing strengths

- unknown/unprofiled tools denied by capability system
- secret filtering for persisted memory/audit paths
- local allowed-root model
- audit records
- approval policy for higher-risk actions
- no unrestricted arbitrary shell exposed as a normal agent tool

### Risks/gaps before self-development

1. Self-development security invariants do not yet exist because the self-development subsystem does not exist.
2. Trusted Local Mode intentionally auto-allows selected low/medium capabilities; tests must continue proving that HIGH-risk actions are not silently auto-approved.
3. Any future self-coding engine must be physically unable (by policy + tests) to silently change:
   - permission engine
   - audit logging
   - secret protection
   - sandbox boundary
   - rollback implementation
   - production activation policy
4. Browser prompt-injection/security tests need significant expansion before Browser V2 is called verified.
5. Sandbox escape tests do not yet exist because the sandbox does not yet exist.

---

## 9. Test gaps

Existing unit/regression tests cover important areas including attachments, memory, permissions/security, V6 compatibility, V7 missions, V7 memory, V7 security, V7 computer use, provider behavior and recent voice helpers.

Major missing test families required for V7.5:

- dedicated integration tests
- evaluation benchmark scenarios
- self-development tests
- rollback tests
- sandbox-escape tests
- offline development tests
- skill generation tests
- capability registry health tests
- gap-detection tests
- workflow-learning tests
- browser prompt-injection/adversarial tests
- DB backup/restore integrity tests
- release-engine tests
- before/after self-improvement benchmark tests

---

## 10. Architecture problems to address in order

### Priority A — before self-development

1. Keep CI green with zero failures/errors.
2. Stabilize package interfaces for tool runtime, permissions, provider metrics and storage.
3. Add Capability Registry.
4. Add Observability/Evaluation primitives that produce objective metrics.
5. Add database backup/integrity primitives required for later rollback.

### Priority B — prerequisites for self-improvement

6. Build a real isolated sandbox/workspace manager.
7. Build Git checkpoint/branch/diff manager.
8. Build immutable self-development security policy.
9. Build rollback manager.
10. Build proposal/evaluation schema.

### Priority C — only after prerequisites are tested

11. Gap detector.
12. Self-development planner/builder/tester/debugger.
13. Self-coding loop.
14. Offline development loop.
15. Skill generation.
16. Workflow-learning proposals.

### Priority D — product and release

17. Mission/Health/Security/Self-Development dashboards.
18. Installer/version cleanup.
19. Backup/restore UI.
20. Full documentation cleanup.
21. Release engine.

---

## 11. Phase-0 conclusion

### Safe to preserve

The current V7 mission, provider, memory, security, computer-use, voice/vision/document, coding and CI foundations should be preserved and evolved incrementally.

### Do not do next

Do **not** immediately give JARVIS uncontrolled self-editing ability.

### Correct next phase

Proceed to **Phase 1 — CI and Stability First** using the current audited branch:

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
```

The CI baseline must remain green on the supported Linux/Python matrix and Windows regression job. Any new warnings/resource leaks discovered locally should be fixed before Phase 2 architecture hardening.

Only after that baseline is confirmed should V7.5 architecture hardening and the new Capability Registry begin.
