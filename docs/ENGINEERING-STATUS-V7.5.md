# JARVIS AI OMEGA — Engineering Status V7.5/V8

Audit branch: `audit/v8-production-hardening`
Audit base commit: `701f52af7eb23f383b2f719515c0a39a2327441a`

This document is the starting inventory for the phased hardening sequence:

`AUDIT → P0 → tests → P1 → tests → P2 → tests → final audit`

No functional feature work should bypass the current phase gate.

## Current architecture

JARVIS is a Windows-first Python desktop agent with a Tkinter desktop UI, provider-neutral AI core, persisted memory, mission orchestration, capability/security gates, browser/computer-use modules, voice input/output, packaging through PyInstaller, and Inno Setup installation.

The public core (`jarvis/core.py`) composes the provider core with memory-aware mission orchestration, audited tool execution, capability registry, model routing, observability, evaluation, workflow learning and lazy self-development. It deliberately keeps provider and local-tool boundaries separate rather than replacing the stable provider core.

Primary layers currently visible in the repository include:

- Desktop/runtime: `desktop_app.py`, `jarvis/runtime_guard.py`, settings/profile UI.
- Accounts: `jarvis/accounts.py`, `jarvis/account_ui.py` and per-profile local storage.
- Agent/missions: `jarvis/agent/*`, persisted mission store/orchestrator and verification outcomes.
- Security: capability policy, permissions, audit integrity, secret/path protections and adversarial tests.
- Computer use: semantic/UIA targeting, OCR fallback, local command routing and Windows controls.
- Browser: public-URL safety, DNS/redirect protection, bounded reads and untrusted-content handling.
- Memory/RAG: conversation memory, V7 memory lifecycle, knowledge/document indexing and backups.
- Voice: microphone/wake-word, continuous interaction, Edge TTS plus fallback and packaged runtime health checks.
- Self-development/skills: sandboxed proposal/test/review/release controls and skill lifecycle.
- Packaging/release: PyInstaller, Inno Setup, SHA-256 manifest, isolated installer validation and in-app updater.

## Existing features

Existing functionality already covers provider chat, deterministic creator identity, per-user local profiles, conversation/history memory, documents, image attachments, voice/TTS, wake phrases, Windows app/settings control, semantic desktop tools, safe browser/research primitives, productivity/reminders, coding/test helpers, updater support, global hotkeys and installation/background startup.

Recent V8 additions include account recovery/profile/avatar flows, user-specific welcome/account display, updater UI, automatic release publishing design, global privacy hotkey and Unicode emoji support.

## Existing security boundaries

The project already follows several strong boundaries:

- unknown/unprofiled tools fail closed;
- high-risk actions remain approval-gated;
- execution and verification are separate outcomes;
- webpage content remains untrusted;
- local/private URL targets are blocked by browser policy;
- file traversal/symlink/junction and secret-like content have regression coverage;
- self-development is sandboxed and production self-modification is disabled by default;
- package validation rejects secrets/private runtime data;
- passwords and recovery codes are stored as salted PBKDF2-HMAC-SHA256 hashes rather than plaintext.

## Existing tests

The test suite is broad and currently includes environment, attachments, UI reliability, diagnostics truthfulness, file security, first-run, hotkeys, HTTP resource lifecycle, provider/inference lifecycle, mission architecture, permission architecture, packaging identity, updater contracts, V7 browser/computer-use/memory/missions/security/self-development/skills, V8 accounts/background/Windows control, Windows release scripts, voice and vision.

The most recent observed full regression run executed 422 tests. The previous rc2 attempt failed only version-consistency documentation checks; the README mismatch was then corrected and a new exact-head run was started.

## Open repository state

- `v7-development` is currently **not protected** and required status checks are not enforced at the branch level.
- Current commits are unsigned.
- Open PR #2 tracks `v7-development → main`.
- Open PR #3 contains earlier V7.5 production-hardening work and documents historical blockers/technical debt.
- CI now contains an end-to-end software release chain: Linux regression → Windows regression → EXE/installer build → isolated installer/repair/uninstall validation → post-packaging regression → GitHub Release publication for `v7-development` only.

## Known bugs / gaps found in this audit pass

### P0/P0-candidate

1. **No P0 may be declared cleared yet.** The current exact rc2 release pipeline has not completed green at the time of this audit snapshot. Until exact-head CI is green, updater/release behavior remains blocked.
2. **New account recovery/profile behavior is under-tested.** Existing V8 account tests cover create/authentication/plaintext rejection/duplicate username/profile environment, but do not directly regression-test recovery-code reset, recovery-code hashing, display-name changes, avatar processing, logout/switch-account behavior or migration from older account schemas. Password recovery is a security-sensitive path and must get deterministic tests before being treated as hardened.
3. **Physical Windows behavior remains unverified.** Automated Windows CI validates software/package/install behavior but does not prove real microphone, audible speaker, foreground focus, UIA/OCR on a user's desktop, multi-monitor/DPI or real browser/app interaction.

### P1

1. Branch protection/rulesets and required CI checks are not enforced.
2. Release commits are unsigned; Windows code signing is not present.
3. Full maintainability debt still includes broad/silent exception handling in multiple modules; these must be reduced without changing behavior blindly.
4. Account/UI responsibilities appear split between `accounts.py` and `account_ui.py`; duplication and ownership boundaries need review before more account UI work.
5. Updater close/restart behavior still needs real-machine validation even after automated installer checks pass.
6. Single-instance handling remains a product reliability gap for background/global-hotkey usage.

### P2/P3 — do not start yet

Smart planner, proactive intelligence, reusable workflows, app awareness, clipboard intelligence, memory control center, richer system health/action history/daily briefing and advanced autonomous behavior remain behind P0/P1 gates. Existing capabilities must be improved rather than duplicated.

## Duplicate functionality to inspect

- Account UI logic exists both inside `run_account_gate()` and in `jarvis/account_ui.py`.
- Historical V6/V7/V7.5 compatibility modules/docs remain alongside current V8 behavior; they should be kept only where compatibility is intentional.
- Local deterministic Windows command routing exists but must be checked for actual integration into the production chat/send path before adding another router.

## Technical debt

- Broad exception swallowing in non-critical presentation/fallback paths.
- Large UI/runtime modules and mixed UI/business logic.
- Hardware-dependent behavior cannot be proven in hosted CI alone.
- No enforced protected release branch.
- No code-signing trust chain yet.
- Some newly added product features have contract/source tests but not full behavior tests.

## Production blockers

A commercial/production-ready claim is blocked by any of the following remaining:

- exact-head CI/release gate not green;
- P0 security/reliability regressions;
- untested security-sensitive account recovery flows;
- missing real Windows device/UI/provider evidence;
- absent branch protection / required checks;
- unsigned Windows releases;
- updater end-to-end close/download/verify/install/restart not proven on a real machine.

## Recommended priority

### Gate A — finish audit/baseline

1. Wait for and record exact-head rc2 CI result.
2. Create baseline report with PASS/FAIL/ERROR/SKIPPED/NOT AVAILABLE states.
3. Inventory tests/security/build/release checks against the master prompt.

### P0

1. Add regression tests for account recovery/profile migrations and security-sensitive password reset behavior.
2. Fix any exact-head CI/release failures without weakening tests.
3. Audit new updater/release path for fail-closed asset selection/checksum/version behavior.
4. Audit startup/background/account switching for state/database corruption risks.

### P1

After P0 tests are green: Windows reliability, UI/voice lifecycle, structured error handling/logging, cleanup, database reliability, CI/release hardening, single-instance behavior and maintainability debt.

### P2

Only after P0/P1 are clear: high-value planner/proactive/workflow/app-awareness/clipboard/file/research/memory/system-health/history features, each with permission, verification, tests and failure handling.

## Audit truth rule

A function existing in source is not proof of a working feature. Automated CI is not proof of physical microphone/speaker/UI behavior. Every later phase report must distinguish IMPLEMENTED, TESTED, VERIFIED, FAILED and NOT VERIFIED explicitly.
