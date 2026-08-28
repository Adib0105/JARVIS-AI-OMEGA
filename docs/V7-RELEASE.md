# JARVIS AI OMEGA V7.5 — Release Guide

This document defines the path from the current V7.5 engineering line to a production release.

## Branch policy

```text
main                 current V7.5 engineering line
short-lived branch   reviewed change / release candidate
v7-development       legacy or in-flight engineering only
```

Do not create a tag or production release merely because code has reached `main`. Release requires code, integration, tests, security evidence and workstation validation.

## Release readiness checklist

A release candidate should satisfy all of the following:

- Linux Python 3.11 regression: PASS
- Linux Python 3.12 regression: PASS
- Linux Python 3.13 regression: PASS
- Linux Python 3.14 regression: PASS
- Windows Python 3.14 regression: PASS
- forced `compileall`: PASS
- full unit/integration/security/evaluation suite: PASS
- `ResourceWarning` gate: PASS
- Windows PyInstaller package smoke: PASS
- package secret/private-data exclusion: PASS
- `self_check.py`: no required failures
- `self_check_v75.py`: no required failures
- real workstation desktop launch: PASS
- voice stop/close behavior: PASS
- core provider chat: PASS
- browser/app control smoke: PASS
- Screen Vision smoke: PASS when enabled
- backup/integrity smoke: PASS

Optional integrations such as Gmail/Calendar or a local model should be validated only if they are included in the release claim.

## Development verification commands

```powershell
git switch main
git pull origin main
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Windows package validation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA-V7.5/JARVIS-OMEGA-V7.5.exe
```

The distribution must not include:

- `.env`
- live `.db`, `.sqlite` or `.sqlite3` runtime data
- `google_token.json`
- `google_credentials.json`
- API keys or OAuth tokens

## Installer validation

With Inno Setup 6 installed:

```powershell
.\build_installer.ps1
```

Validate:

1. clean install;
2. launch from installed location;
3. desktop/start-menu shortcuts if configured;
4. first-run configuration behavior;
5. upgrade behavior if supported;
6. uninstall without deleting unrelated user files;
7. secrets/runtime databases are not embedded in installer payload.

## Controlled self-development release path

Self-generated improvements follow a separate guarded pipeline:

```text
Gap → Proposal → Sandbox → Build → Tests → Debug → Security/Evaluation
→ Diff → AWAITING_APPROVAL → APPROVED → Controlled Release → Post-test
```

Important rules:

- `APPROVED` does not mean `DEPLOYED`;
- production self-modification is disabled by default;
- the reviewed production HEAD must still match;
- production worktree must be clean;
- exact reviewed files and policy checks must pass;
- deployment is fast-forward only;
- no force-reset/force-merge release path;
- rollback is history-preserving.

## Rollback

The tested rollback model uses `git revert` plus regression verification rather than destructive `git reset --hard`.

Before any release, record the known-good commit/tag. If a deployed improvement fails post-release checks, revert the deployment commit(s), rerun the regression suite and confirm the known-good behavior is restored.

## Documentation before release

Update together:

- `README.md`
- `CHANGELOG.md`
- `docs/V7.5-STATUS.md`
- `ROADMAP.md`
- this release guide if release gates change

Do not label an experimental feature as stable merely because its deterministic tests pass.

## Tagging convention

Recommended release tags:

```text
v7.5.0
v7.5.1
v7.6.0
```

Use semantic versioning:

- PATCH — compatible fixes
- MINOR — compatible feature additions
- MAJOR — intentional compatibility-breaking change

## Release notes structure

Each release should state:

- headline capabilities
- reliability/security changes
- known limitations
- optional dependencies
- upgrade instructions
- migration/data notes
- tested platforms/Python versions
- rollback instructions

## Final rule

A green CI run is necessary but not sufficient for a Windows desktop release. Physical microphone behavior, screen permissions, provider availability, packaged launch, installer behavior and installed-app interaction require workstation smoke testing before V7.5 can move beyond BETA.
