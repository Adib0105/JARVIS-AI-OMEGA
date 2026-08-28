# Changelog

All notable engineering changes to JARVIS AI OMEGA are documented here.

## 7.5.0 production-hardening candidate — unreleased

### Fixed

- Fixed deferred Tk worker error callbacks that could reference Python's cleared exception variable and fail before showing the real error.
- Replaced false mission completion for partially verified outcomes with a terminal `PARTIAL` state and excluded partial/cancelled outcomes from success metrics.
- Added legal mission transitions, atomic state/event persistence and optimistic concurrency revisions to prevent stale processes overwriting newer mission state.
- Closed Browser V2 DNS/redirect SSRF gaps with public DNS validation on every hop, validated-address connection pinning, bounded content handling and active-HTML stripping.
- Closed self-development review/commit gaps for untracked files, symlinks, binary/oversized content and same-file-set time-of-check/time-of-use mutation.
- Replaced the updater's generic URL opener with a fixed HTTPS GitHub API connection and canonical release-link validation.

### Hardened / normalized

- Protected the complete self-development control plane, adjacent runtime trust boundaries, release-critical tests and CI workflows from automated self-modification.
- Added canonical tool outcomes and machine-readable security contracts for every exposed tool.
- Added a committed capability inventory with implementation, entry point, dependency, permission, risk, evidence and limitation fields.
- Centralized version/product/artifact names at `7.5.0`, moved builds/installers to V7.5 naming and removed the stale V7 installer definition.
- Added bounded direct requirements, exact constraints, pinned audit tooling and CI gates for correctness lint, high-severity static security findings and dependency vulnerabilities.
- Reconciled branch, release and historical-document claims. The candidate remains BETA pending current CI and real Windows/provider/hardware/installer evidence.

## V7 / V7.5 engineering track — unreleased

### Reliability and architecture
- Added provider-neutral contracts and typed error/configuration foundations.
- Added persisted mission state with verification, retry, recovery, replanning, pause/resume/cancel.
- Added deterministic SQLite connection cleanup and Windows regression coverage.
- Added explicit permission-checker dependency injection for the V7 tool runtime.
- Added runtime-derived Capability Registry rather than hard-coded capability claims.
- Added V7.5 engineering self-checks covering health, capabilities, memory lifecycle, backup integrity, self-development, release/skills and optional OCR/offline dependencies.

### Security
- Added capability-based security profiles, Approval Center and audit evidence.
- Added Trusted Local Mode for ordinary allowlisted LOW/MEDIUM local actions without removing high-risk boundaries.
- Added immutable self-development policy for security/audit/secret/sandbox/rollback/production-activation controls.
- Added public-browser private-target blocking and prompt-injection scanning.
- Added adversarial regression cases for injection, secret extraction/persistence, permission bypass, sandbox escape and unrestricted shell exposure.
- Expanded repository security policy with vulnerability-reporting guidance, capability/verification rules, computer-use safety, protected self-development boundaries and release/rollback requirements.

### Memory / RAG / documents
- Preserved V7 working/episodic/semantic/procedural memory and hybrid context retrieval.
- Added content-hash document provenance and unchanged/update/duplicate indexing decisions.
- Added additive memory lifecycle support for reinforcement, contradiction detection, superseding and stale/confidence decay without replacing legacy V7 memory data.

### Computer / browser / coding
- Preserved semantic Windows UI Automation and confidence/no-guess targeting.
- Integrated optional local OCR fallback behind a stricter confidence gate: UIA is attempted first, ambiguous UIA never falls through to OCR, and OCR actions remain PARTIAL until independently verified.
- Added Browser V2 public-target trust checks, local/private-address blocking and prompt-injection isolation.
- Fixed BrowserAgent plain-text extraction normalization and URL error-contract regressions.
- Added Coding Agent V2 workflow coordination over approved project edit/test/Git primitives.

### Self evaluation and development
- Added historical self-evaluation metrics derived from mission/audit evidence.
- Added capability gap detection from registry state, measured metrics and repeated failures.
- Added persisted improvement proposals and isolated `self-improvement/IMP-*` Git worktrees.
- Added sandbox-only builder, full regression tester, bounded self-debugger and objective diff evaluator.
- Added JSON-only self-coding output contract with immutable-core/path/change-size gates.
- Added optional provider-neutral offline development through an explicitly configured local OpenAI-compatible model.
- Added deterministic before/after agent benchmark and self-improvement benchmark binding.

### Skills / workflow learning
- Added skill manifest/proposal registry with version, permissions, risk, tests, documentation and evaluation metadata.
- Added repeated safe-workflow learning that proposes reusable workflows without silent activation.
- Added skill sandbox build pipeline reusing self-development tests/security/diff gates.
- Added deployed-only skill activation: linked improvement must be `DEPLOYED`, required files must exist, evaluation must be PASS/VERIFIED and operator activation must be explicit.
- Added SKILLS tab in Agent Command Center plus public runtime APIs for prepare/build/activate/disable.

### Observability / health / cost
- Added structured local observability for model/mission/system/self-development events.
- Added provider/model/fallback/latency/token usage tracking with credential-safe usage sanitization.
- Cost is recorded only when a provider explicitly reports a numeric cost; otherwise it remains N/A.
- Added PASS/WARNING/FAIL Health System with SQLite integrity, provider config, local AI, vision, voice, mic, Google, coding/Git, computer use and sandbox checks.

### Operator UI
- Added V7.5 Agent Command Center with Mission, Health, Capabilities, Observability, Security, Self Development and Data/Backup views.
- Added guarded RELEASE tab for controlled deploy/rollback operations.
- Added SKILLS tab for gap-driven skill proposal/build/activation/disable lifecycle.
- Added voice media controls: play/pause, stop, runtime speed adjustment and close-window playback termination.

### Data safety
- Added SQLite backup API, SHA-256 manifest, schema/integrity verification and export archive.
- Restore/import requires destructive confirmation and creates a pre-restore backup.
- Added active-database integrity diagnostic API used by local self-check/health flows.
- Portable exports/builds do not bundle `.env`, OAuth tokens, API keys or the live database.

### Controlled release / rollback
- Added experimental controlled release engine requiring explicit approval plus `PRODUCTION_SELF_MODIFICATION=true`.
- Release requires fresh tests, immutable-core policy pass, exact reviewed files, clean production worktree, unchanged expected HEAD and fast-forward-only Git deployment.
- Rollback uses history-preserving `git revert` plus regression verification rather than destructive `reset --hard`.
- Command Center release controls cannot bypass these gates.
- Safe default remains `PRODUCTION_SELF_MODIFICATION=false`.

### CI / packaging
- Expanded CI to Linux Python 3.11/3.12/3.13/3.14 plus Windows Python 3.14.
- CI forces compilation, runs full unittest/security/evaluation discovery and treats `ResourceWarning` as an error.
- Added Windows PyInstaller package smoke job after Windows regression.
- Package smoke explicitly installs build dependencies and rejects bundled `.env`, live DB/SQLite files and Google OAuth tokens/credentials.
- Updated Windows build and Inno Setup installer definitions to V7 naming and secret-safe packaging.

### Documentation / GitHub experience
- Rebuilt the main README into a structured project landing page with architecture, status, setup, feature, safety, testing and release navigation.
- Added `docs/README.md` as the documentation hub.
- Added a complete Windows V7.5 setup guide.
- Added a dedicated troubleshooting guide for provider, voice, computer-use, SQLite, self-development, packaging and installer issues.
- Added a release/readiness/rollback guide.
- Added a transparent top-level `ROADMAP.md` separating verified, experimental and release-candidate work.
- Refreshed architecture, mission/agent and testing documentation to current V7.5 behavior.
- Expanded `CONTRIBUTING.md` with quality, verification, security, computer-use and self-development contribution requirements.
- Added structured GitHub bug-report and feature-request forms.
- Added a pull-request template with testing, security, evidence and rollback checklists.
- README and Capability Registry distinguish verified foundations from optional/experimental operator-gated systems.

## V7 foundation
- Provider abstraction, mission orchestration, verification/recovery, capability security, layered memory/context and semantic computer-use foundations.

## V6
- ARC desktop HUD, multimodal image/screen vision, spoken Hindi/Hinglish output, productivity/document/coding tools, local memory, public web tools and Windows packaging foundations.
