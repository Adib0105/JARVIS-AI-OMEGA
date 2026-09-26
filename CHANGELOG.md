# Changelog

All notable engineering changes to JARVIS AI OMEGA are documented here.

## V7.7 five-layer intelligence — unreleased

- Added an ordered AI → Machine Learning → Deep Learning → Generative AI → LLM routing runtime for chat, vision and specialist model selection.
- Added a bounded local online intent classifier for English, Hindi and Hinglish vocabulary; it learns only from successful routes, stores token fingerprints instead of prompt text, rejects secret-like input and supports operator reset.
- Added optional embedding-based neural semantic routing behind explicit configuration. It cannot override specialist routes and influences a generic route only when the local ML signal agrees.
- Added grounded generation modes and final FAST / SMART / CODING / PLANNING / REVIEW / SUMMARY / VISION / LOCAL model selection without bypassing capability permissions, audit or verification.
- Added an INTELLIGENCE Command Center view, dynamic V7.7 desktop labels, runtime status/reset APIs, capability reporting and privacy-safe route observability.
- Added configuration validation, self-check coverage and deterministic regression tests for ordering, safety, adaptation, corruption recovery, secret rejection, reset and neural consensus.
- Versioned source, installer defaults and CI-built installers as V7.7.
- This is software evidence, not a claim of human-level intelligence or zero defects. Real Windows microphone/tray/focus and installation soak evidence remains a release gate.

## V7.6 background/account launch pack — unreleased

- Background listening now reports READY only after Vosk loads and Windows actually opens the microphone.
- “Wake up Jarvis” now answers “Yes boss, kya chahiye?”, releases the hotword stream, listens for one offline follow-up command, and safely restarts hotword listening.
- Wake actions stay in the tray by default instead of stealing focus from Chrome or the current foreground app.
- Device loss keeps the tray alive and retries with bounded 3/10/30/60/120-second backoff.
- Added secure local multi-user profiles: salted PBKDF2 password digests, bounded lockout, remembered background sessions, per-profile data, sign-out/switch-user and name-aware greetings.
- Added the permission-gated 20-action Windows Power Pack for media, active windows, virtual desktops, workstation lock and Windows Settings.
- These changes are release-candidate code. Real Windows microphone, clean-install, upgrade, installer, Defender and subscription-backend validation remain required before public sale.

## Remaining-blocker hardening — unreleased, release blocked

- Fail closed for generated/project test execution until OS isolation is validated.
- Selectively port revisioned mission persistence, legal transitions, address-pinned public reading and protected control-plane policy from existing hardening branches.
- Reduce false verification, redact tested persistence paths, preserve coding routing and response evidence, filter irrelevant retrieval, bound local reads and use SQLite online migration backups.
- Enforce enabled tool schemas before dispatch and serialize connection save/apply inside one process.
- Add deterministic adversarial regressions and retain Windows packaging/Defender gates; disable publication while mandatory findings remain unresolved.
- Local Linux: 369 tests passed. Windows, transactional rollback and production readiness are not verified. Full evidence and open findings: `docs/FINAL-HARDENING-AUDIT.md`.

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
