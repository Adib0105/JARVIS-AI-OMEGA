# JARVIS AI OMEGA V7.5/V8 — Hardening Audit

This is the current phase handoff required by the V7.5/V8 engineering brief. It is **not** a production-readiness certificate. Exact-change GitHub CI and physical/live evidence remain separate gates.

## 1. What was already present

Provider-neutral chat, persisted missions, capability permissions, approval/audit controls, browser/file security, memory/RAG lifecycle, voice/TTS logic, Windows controls, observability, evaluation, skills, controlled self-development, updater, PyInstaller/Inno packaging and extensive regression coverage.

## 2. What was fixed

- Password-recovery replay and unbounded recovery input.
- Silent recovery update for nonexistent accounts.
- Non-atomic avatar replacement and missing image size/dimension bounds.
- Optional battery sensor failure hiding all resource metrics.
- Release self-check inspecting lifecycle state before additive DB migration.

## 3. What was newly added

Deterministic tests for recovery hashing/failure/success/replay prevention/rotation, legacy account migration, active-profile round trip, avatar normalization, optional-sensor degradation and fresh-profile release migration.

## 4. Security fixes

Recovery codes remain salted hashes, become one-time after successful use and are limited to 6–200 characters. Oversized authentication input is rejected before expensive derivation. Avatar inputs are bounded and replaced atomically.

## 5. Performance improvements

Oversized password/recovery input no longer enters PBKDF2. Resource monitoring continues when an optional battery probe is unavailable.

## 6. UI/UX improvements

Account UI now explains that recovery codes are one-time and tells the user to set a new code after a successful reset.

## 7. Tests added

Nine deterministic regression tests across accounts, resource monitoring and release database preparation.

## 8. Tests passed

432 automated tests passed on Linux/Python 3.12.13. Critical Ruff, high-severity Bandit, `pip check` and core `pip-audit` passed.

## 9. Tests failed

No unit/regression test failed. Full Ruff remains a non-green debt inventory with 509 findings. The exact Windows constraint audit is not resolvable on Linux Python 3.12.

## 10. Windows verification status

Software contracts are automated; exact-change GitHub CI is required. Physical Windows GUI, UIA/OCR, multi-monitor/DPI, microphone and audible speaker evidence is NOT VERIFIED.

## 11. Installer verification status

The repository has an automated isolated installer chain. Older workflow evidence cannot certify this new change; exact-change CI and human clean-machine UX remain pending.

## 12. Remaining known issues

Full Ruff debt, broad/silent exception handling, large mixed-responsibility UI modules, single-instance/background ownership, code signing and live-device/provider evidence.

## 13. Production blockers

- exact-change CI not yet recorded;
- branch protection/required checks absent;
- unsigned source/release/Windows artifacts;
- physical Windows/device/live-provider validation absent;
- real updater close/install/restart UX not proven on a workstation.

## 14. Recommended next version

Continue V8 hardening through bounded P1 work: single-instance/background lifecycle, targeted exception cleanup, provider/runtime lifecycle evidence and exact Windows smoke capture. Do not start broad P3 autonomy while these gates remain.

## BEFORE

- Account recovery could be replayed and important profile behaviors lacked coverage.
- Optional battery failure could suppress all system metrics.
- Fresh release self-check could fail before initializing the lifecycle schema.

## AFTER

- Recovery/profile/resource/release-init paths are hardened and covered.
- 432 tests and critical software/security gates pass locally.
- Evidence boundaries are documented without promoting automated checks to device verification.

## REMAINING

The exact unresolved items are listed in sections 12 and 13 and in `docs/KNOWN-LIMITATIONS.md`.
