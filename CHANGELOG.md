# Changelog

All notable engineering changes to JARVIS AI OMEGA are documented here.

## V7 / V7.5 engineering track — unreleased

### Reliability and architecture
- Added provider-neutral contracts and typed error/configuration foundations.
- Added persisted mission state with verification, retry, recovery, replanning, pause/resume/cancel.
- Added deterministic SQLite connection cleanup and Windows regression coverage.
- Added explicit permission-checker dependency injection for the V7 tool runtime.
- Added runtime-derived Capability Registry rather than hard-coded capability claims.

### Security
- Added capability-based security profiles, Approval Center and audit evidence.
- Added Trusted Local Mode for ordinary allowlisted LOW/MEDIUM local actions without removing high-risk boundaries.
- Added immutable self-development policy for security/audit/secret/sandbox/rollback/production-activation controls.
- Added public-browser private-target blocking and prompt-injection scanning.
- Added adversarial regression cases for injection, secret extraction/persistence, permission bypass, sandbox escape and unrestricted shell exposure.

### Memory / RAG / documents
- Preserved V7 working/episodic/semantic/procedural memory and hybrid context retrieval.
- Added content-hash document provenance and unchanged/update/duplicate indexing decisions.
- Added schema-safe memory lifecycle foundation for reinforcement, contradiction detection, superseding and stale/confidence decay.

### Computer / browser / coding
- Preserved semantic Windows UI Automation and confidence/no-guess targeting.
- Added optional local OCR target fallback foundation; final action-engine integration remains experimental.
- Added Browser V2 trust/injection isolation and fixed plain-text extraction normalization.
- Added explicit Coding Agent V2 workflow coordinator over approved project edit/test/Git primitives.

### Self evaluation and development
- Added historical self-evaluation metrics derived from mission/audit evidence.
- Added capability gap detection from registry state, measured metrics and repeated failures.
- Added persisted improvement proposals and isolated `self-improvement/IMP-*` Git worktrees.
- Added sandbox-only builder, full regression tester, bounded self-debugger and objective diff evaluator.
- Added JSON-only self-coding output contract with immutable-core/path/change-size gates.
- Added optional provider-neutral offline development through an explicitly configured local OpenAI-compatible model.
- Added skill proposal/manifests, repeated workflow learning and sandboxed skill build foundation.
- Added deterministic before/after agent benchmark and self-improvement benchmark binding.

### Observability / health / cost
- Added structured local observability for model/mission/system/self-development events.
- Added provider/model/fallback/latency/token usage tracking.
- Cost is recorded only when a provider explicitly reports a numeric cost; otherwise it remains N/A.
- Added PASS/WARNING/FAIL Health System with SQLite integrity, provider config, local AI, vision, voice, mic, Google, coding/Git, computer use and sandbox checks.

### Operator UI
- Added V7.5 Agent Command Center with Mission, Health, Capabilities, Observability, Security, Self Development and Data/Backup views.
- Added voice media controls: play/pause, stop, runtime speed adjustment and close-window playback termination.

### Data safety
- Added SQLite backup API, SHA-256 manifest, schema/integrity verification and export archive.
- Restore/import requires destructive confirmation and creates a pre-restore backup.
- Portable exports/builds do not bundle `.env`, OAuth tokens, API keys or the live database.

### Controlled release / rollback
- Added experimental controlled release engine requiring explicit approval plus `PRODUCTION_SELF_MODIFICATION=true`.
- Release requires fresh tests, immutable-core policy pass, exact reviewed files, clean production worktree, unchanged expected HEAD and fast-forward-only Git deployment.
- Rollback uses history-preserving `git revert` plus regression verification rather than destructive `reset --hard`.
- Safe default remains `PRODUCTION_SELF_MODIFICATION=false`.

### CI / packaging
- Expanded CI to Linux Python 3.11/3.12/3.13/3.14 plus Windows Python 3.14.
- CI forces compilation, runs full unittest discovery and treats `ResourceWarning` as an error.
- Updated Windows build and Inno Setup installer definitions to V7 naming and secret-safe packaging.

### Documentation
- Added repository audit, self-development, offline, browser, tools, testing and V7.5 status documentation.
- README now distinguishes implemented, experimental and validation-stage systems.

## V7 foundation
- Provider abstraction, mission orchestration, verification/recovery, capability security, layered memory/context and semantic computer-use foundations.

## V6
- ARC desktop HUD, multimodal image/screen vision, spoken Hindi/Hinglish output, productivity/document/coding tools, local memory, public web tools and Windows packaging foundations.
