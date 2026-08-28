# JARVIS AI OMEGA 8.0.0-rc2 — Baseline Report

Date: 2026-08-28  
Branch: `audit/v8-production-hardening`  
Baseline parent: `4debd3691bbe8eff7e2d29c0f253b829fb984f9b`  
Environment: Linux, Python 3.12.13, isolated virtual environment

This report distinguishes a check result from real Windows, device, provider or installer evidence. The commit containing this report requires its own green GitHub workflow before it inherits any automated Windows/package status.

## Baseline before the hardening changes

| Check | Status | Evidence |
|---|---|---|
| Repository/PR inspection | PASS | Existing branches and PRs were reviewed; this branch continues draft PR #4 and does not modify `main`. |
| Compileall | PASS | `python -m compileall -f -q .` on Python 3.12.13. |
| Full unit/regression suite | PASS | 422 tests passed in 9.369 seconds. |
| Linux Windows-junction test | SKIPPED | One test is guarded by `os.name == 'nt'`; it is expected to execute in Windows CI. |
| Exact-parent GitHub workflow | PASS | Workflow run 33179310641 completed successfully for parent `4debd369`. |
| Critical Ruff (`E9,F63,F7,F82`) | PASS | No critical syntax/name errors. |
| Full Ruff | FAIL | 509 maintainability findings: 229 `BLE001`, 77 `S110`, 61 import-order findings and smaller groups. This is recorded debt, not hidden or auto-fixed. |
| Bandit high severity | PASS | Recursive high-severity scan of runtime/source entry points found no high-severity result. |
| Core dependency audit | PASS | `pip-audit -r requirements.txt`: no known vulnerabilities found. |
| Exact release-constraint audit on Linux 3.12 | NOT AVAILABLE | The Windows/Python 3.13+ `audioop-lts==0.2.2` pin cannot resolve on Linux Python 3.12. Exact Windows dependency resolution remains a Python 3.14.7 CI gate. |
| `pip check` | PASS | No broken requirements found. |
| Release self-check | FAIL | Fresh DB lifecycle initialization and optional battery-probe handling exposed real failures; both are fixed and regression-tested in this change. |
| Local Windows EXE/Inno build | NOT AVAILABLE | Linux environment cannot execute the Windows packaging toolchain. |
| Physical Windows GUI/UIA/OCR | NOT AVAILABLE | Requires exact-candidate workstation evidence. |
| Microphone/audible speaker | NOT AVAILABLE | Requires physical device evidence. |
| Live provider request | NOT AVAILABLE | No live credential/request was used. |

## Result after this hardening phase

| Check | Status | Evidence |
|---|---|---|
| Compileall | PASS | Full source compilation completed. |
| Full unit/regression suite | PASS | 432 tests passed. |
| Linux Windows-junction test | SKIPPED | One expected Windows-only test. |
| Focused account/observability/release tests | PASS | 32 focused tests passed before the complete rerun. |
| Critical Ruff | PASS | `E9,F63,F7,F82` clean. |
| Bandit high severity | PASS | No high-severity finding in the scanned runtime/source paths. |
| `pip check` | PASS | No broken requirements. |
| Core dependency audit | PASS | No known vulnerabilities in `requirements.txt`. |
| Full Ruff | FAIL | Existing repository-wide maintainability debt remains; no bulk behavior-changing rewrite was attempted. |
| GitHub CI for this change | NOT AVAILABLE | Must run on the exact pushed commit; older green evidence is not reused. |
| Physical/live validation | NOT AVAILABLE | See `docs/WINDOWS-E2E-CHECKLIST.md`. |

## Baseline findings fixed here

1. Password-recovery codes are now bounded, hashed and consumed after a successful reset to prevent replay.
2. Recovery-code rotation fails explicitly for a missing account instead of silently claiming success.
3. Legacy account schemas migrate recovery columns without losing authentication data.
4. Avatar processing is size/dimension bounded and writes through an atomic temporary replacement.
5. An unavailable optional battery sensor no longer hides CPU, memory, disk, process and network metrics.
6. The release self-check applies additive DB migration before checking the V7.5 memory lifecycle.

## Remaining baseline blockers

- Exact-change GitHub CI is pending until this commit is pushed.
- Full Ruff debt remains at the repository level.
- Branch protection and required checks are repository settings and remain unenforced.
- Code signing/AuthentiCode is absent.
- Real Windows device, live provider, microphone, speaker, UIA/OCR, multi-monitor/DPI and human installer UX evidence is absent.
