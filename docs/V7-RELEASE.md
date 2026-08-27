# JARVIS AI OMEGA 8.0.0-rc1 — Release Guide

The filename is retained for historical links. The release authority is `jarvis.version.APP_VERSION`; this guide must not define a second application version.

## Release principle

A release requires evidence for the exact commit being shipped. Evidence from an older commit does not carry forward after source, dependency, packaging or installer changes.

```text
SOURCE
→ compile + regression
→ Windows regression
→ frozen EXE
→ package healthchecks
→ installer
→ isolated install/uninstall
→ post-packaging regression
→ real Windows/device/live-provider evidence
```

A green CI workflow is necessary, but it is not proof of microphone capture, audible TTS, real desktop interaction, DPI/focus behavior or live provider inference.

## Branch policy

- `v7-development` — current engineering/release-candidate branch.
- `main` — separate stable line; do not infer its application version from this document.

Before a stable release, repository administrators should enable branch protection/rulesets with the required CI checks. Repository policy is separate from application source code.

## Automated release gate

For the exact release commit, CI must pass all of the following:

- Linux Python 3.11 regression;
- Linux Python 3.12 regression;
- Linux Python 3.13 regression;
- Linux Python 3.14 regression;
- Windows Python 3.14.7 regression;
- forced `compileall`;
- full unit/integration/security/evaluation suite;
- `ResourceWarning` enforcement;
- constrained dependency installation;
- frozen `JARVIS-OMEGA.exe` build;
- canonical Windows PE file/product version metadata verification;
- packaged first-run healthcheck;
- packaged application healthcheck;
- packaged TTS-worker/runtime healthcheck;
- release-bundle secret/private-data exclusion;
- Inno Setup installer build;
- installer SHA-256 evidence;
- isolated install without repository checkout or Python setup;
- installed-app healthchecks;
- shortcut and uninstaller validation;
- uninstall with user-data preservation;
- post-packaging full regression.

## Development verification commands

```powershell
git switch v7-development
git pull origin v7-development
.\setup_windows.ps1 -IncludeBuildTools
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`self_check_v75.py` remains a backward-compatible wrapper around the canonical release self-check and is not an independent release authority.

## Reproducible Windows environment

The release build baseline is:

```text
Python 3.14.7
pip 26.2.1
PyInstaller 6.22.2
Inno Setup 6.7.1
```

Dependencies must be installed through the checked-in requirements plus `constraints-release.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.2.1
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt
```

See [DEPENDENCIES.md](DEPENDENCIES.md).

## Windows package validation

```powershell
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA/JARVIS-OMEGA.exe
```

`build_windows.ps1` generates the PyInstaller Windows version resource from `jarvis.version`, embeds it in the executable and verifies the built PE metadata before declaring the build ready.

The distribution must not include private runtime material such as:

- `.env`;
- live `.db`, `.sqlite` or `.sqlite3` data;
- Google OAuth credentials/tokens;
- API keys, passwords or private keys.

## Installer validation

With Inno Setup 6.7.1 installed:

```powershell
.\build_installer.ps1
```

The installer filename is derived from the canonical release version. For this candidate:

```text
dist/installer/JARVIS-AI-OMEGA-Setup-8.0.0-rc1.exe
```

Validate that `dist/installer/SHA256.txt` matches the installer itself.

The active installer definition is `installer/JarvisOmega.iss`.

## Manual Windows E2E gate

Use [WINDOWS-E2E-CHECKLIST.md](WINDOWS-E2E-CHECKLIST.md) and record evidence against the exact commit/package. Required claims should remain `NOT VERIFIED` until actually exercised.

Manual areas include:

- normal GUI startup/shutdown/relaunch;
- real Chrome and Notepad interaction;
- UIA targeting, focus changes and wrong/missing targets;
- screenshot/OCR behavior on the actual display;
- keyboard and mouse effects with post-action verification;
- microphone capture and speech recognition;
- audible speaker TTS;
- real provider response with an actual configured credential;
- invalid credential, timeout/rate-limit/unavailable-model behavior where practical;
- DPI/resolution/window-movement behavior;
- disconnect/reconnect behavior;
- clean installed first run and uninstall on a real workstation.

## Controlled self-development release path

Self-generated improvements remain guarded:

```text
Gap → Proposal → Sandbox → Build → Tests → Security/Evaluation
→ Diff → AWAITING_APPROVAL → APPROVED → Controlled Release → Post-test
```

Rules:

- `APPROVED` does not mean `DEPLOYED`;
- production self-modification is disabled by default;
- reviewed production HEAD and reviewed files must still match;
- production worktree must be clean;
- security/tests/evaluation must pass;
- deployment is fast-forward only;
- rollback is history-preserving.

## Rollback

Record the known-good commit/tag before release. If a deployed change fails, use history-preserving revert, rerun the complete release gate and confirm the restored behavior. Do not hide a regression with destructive history rewriting.

## Release notes

Release notes should state:

- exact commit/tag;
- headline capabilities;
- reliability/security changes;
- known limitations;
- dependency/build baseline;
- automated CI run used as evidence;
- manual Windows/device/live-provider evidence status;
- upgrade/migration notes;
- rollback instructions;
- installer SHA-256.

Recommended candidate/stable tags follow the canonical major version, for example:

```text
v8.0.0-rc1
v8.0.0
```

## Final rule

Do not call the candidate fully verified or production-ready while a required exact-commit CI gate is red or required real-device/live-service evidence is still `NOT VERIFIED`.
