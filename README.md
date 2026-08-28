# JARVIS AI OMEGA 8.0.0-rc2 — Release Candidate

JARVIS AI OMEGA is a Windows-first desktop AI agent built around an evidence-driven execution loop:

```text
UNDERSTAND → PLAN → PERMISSION → EXECUTE → VERIFY → RECOVER / REPLAN
```

This repository does **not** treat import success, a green unit test, or an accepted OS input event as proof that a physical device, live provider, or real UI action worked.

## Release truth model

Documentation uses these categories:

- **VERIFIED** — qualifying evidence for the exact release candidate exists.
- **TESTED** — exercised by automated tests, but not necessarily on a real user's device/service.
- **EXPERIMENTAL** — implemented but intentionally not a stable release claim.
- **LIMITED** — implemented with a known architectural or environmental limitation.
- **NOT VERIFIED** — no qualifying real-device/live-service evidence exists for the exact candidate.
- **PLANNED** — not implemented as a release capability.

Runtime diagnostics use the more precise states `INSTALLED`, `CONFIGURED`, `LOCAL_FUNCTIONAL`, `INTEGRATION_TESTED`, `DEVICE_VERIFIED`, `E2E_VERIFIED`, `DEGRADED`, `FAILED`, and `NOT_TESTED`.

## Current engineering status

| Area | Status | What that means |
|---|---|---|
| Canonical application version | TESTED | `jarvis.version.APP_VERSION` is the release authority; package/config/build/installer/self-check derive from it. Exact-commit CI must still pass before release evidence is accepted. |
| Capability permission authority | TESTED | Active and legacy permission entry points delegate to the capability-based canonical policy. High-risk actions remain approval-controlled. |
| Public mission pipeline | TESTED | `jarvis.core.JarvisOmega` uses the persisted memory-aware orchestrator, tool evidence, verification, recovery/replanning and observability. |
| Compatibility mission entry point | TESTED | `jarvis.core_v7.JarvisOmega.run_mission()` is an orchestrator wrapper using the audited recording tool runtime; the duplicated legacy mission loop has been removed. |
| Provider/model routing | TESTED | Contract, timeout, error classification and fallback behavior are automated. Real provider inference is NOT VERIFIED until tested with a real credential on the exact packaged build. |
| Response-quality runtime | TESTED | Stable free-text routing, deterministic local identity handling, garbled-response repair and desktop cleanup are composed directly into `JarvisOmega`; startup no longer monkey-patches `chat()` or `_select_model()`. |
| Runtime/UI composition | TESTED | Voice controls and RELEASE/SKILLS Command Center features are composed through subclasses. Historical installer functions remain no-op compatibility shims; packaged startup no longer mutates core or UI classes. |
| Computer Use V2 logic | TESTED | UIA-first targeting, ambiguity rejection, OCR fallback and partial/unverified evidence behavior are automated. Real desktop/UI/device E2E is NOT VERIFIED. |
| Voice/TTS worker/package path | TESTED | Frozen-worker routing and software state transitions are automated. Audible speaker output is NOT VERIFIED unless a person actually hears the exact packaged build. |
| Microphone/speech input | LIMITED | Package/config presence can be diagnosed; physical microphone capture/recognition is NOT VERIFIED without a real device test. |
| File access security | TESTED | Allowed-root resolution, traversal, symlink/junction escape, sensitive path/type and secret-content boundaries have regression coverage. |
| Browser/web security | TESTED | Public URL policy, private/local target blocking and prompt-injection isolation have automated coverage. |
| Memory / persistence / backup | TESTED | Schema migration, memory lifecycle, secret persistence blocking, backup/integrity and restore gates are automated. |
| Observability / redaction | TESTED | Provider/tool/verification/failure metadata and secret redaction are covered; unsupported cost/success metrics are not fabricated. |
| Controlled self-development | EXPERIMENTAL | Sandbox/test/benchmark/approval/release/rollback controls exist. Production self-modification remains disabled by default. |
| Skill lifecycle runtime | TESTED | Skill build/activation methods are declared directly on the public core; the historical installer function is now a no-op compatibility shim. |
| Windows EXE + installer CI | TESTED | CI builds the frozen EXE and installer, runs package healthchecks and performs isolated install/uninstall validation. This is not a substitute for human GUI/device E2E. |
| Real Windows GUI/device/live-provider E2E | NOT VERIFIED | Must be recorded separately for the exact candidate using the Windows E2E checklist. |

## Versioning

The canonical release source is:

```python
from jarvis.version import APP_VERSION
```

Current release candidate:

```text
8.0.0-rc2
```

Do not add another hard-coded application version in runtime configuration, diagnostics, packaging metadata, installer scripts or CI. Windows numeric file-version metadata is derived from the canonical release version.

The packaged executable uses the stable product identity `JARVIS-OMEGA.exe`; the release version belongs in product metadata and the installer filename, not in the executable path. This keeps shortcuts, automation and upgrade paths stable across future releases.

## Security boundary

Tool requests follow the capability/security policy before execution. The intended flow is:

```text
Tool request
→ capability/risk classification
→ canonical permission checker
→ user confirmation when required
→ execution
→ verification/evidence
→ audit
```

Unknown/unprofiled tools fail closed. Trusted Local Mode does not bypass high-risk keyboard control, destructive actions, credential boundaries, production release controls, or protected self-development areas.

Never commit `.env`, API keys, OAuth tokens, passwords, private keys, live databases, or other credentials/private runtime data.

## Mission execution

Preferred production entry point:

```python
from jarvis.core import JarvisOmega
```

The public core uses the persisted memory-aware mission orchestrator and evidence-aware tool runtime. The older `jarvis.core_v7.JarvisOmega.run_mission()` API remains only for compatibility, but it now delegates to the persisted orchestrator instead of running an independent mission loop.

## Computer use

Targeting strategy:

```text
Windows UI Automation / semantic targeting
→ confidence + ambiguity gate
→ OCR fallback when configured
→ coordinate fallback only when justified
→ action
→ observation
→ expected state change
→ verification
```

Important actions are not considered verified merely because Windows accepted mouse/keyboard input. If the expected result cannot be observed, the result must remain partial/unverified rather than being upgraded to success.

## Diagnostics

Run the canonical release self-check:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_release.py
```

`self_check_v75.py` remains only as a backward-compatible wrapper for historical automation.

`self_check.py` distinguishes package installation from configuration, local functionality, physical-device verification and live/E2E verification. It intentionally reports microphone, audible TTS, real computer-use device behavior and live provider inference as `NOT_TESTED` unless those checks were actually performed elsewhere with qualifying evidence.

## Reproducible dependency environment

Runtime, Windows and build dependencies are exact-pinned and CI consumes `constraints-release.txt`.

Windows release build baseline:

```text
Python 3.14.7
pip 26.2.1
PyInstaller 6.22.2
Inno Setup 6.7.1
```

Reproduce the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.2.1
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt
```

See [Dependency reproduction](docs/DEPENDENCIES.md).

## Quick start — source checkout

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
git switch v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Create/update local configuration without committing secrets:

```powershell
Copy-Item .env.example .env
```

Example OpenRouter configuration:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-secret>
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Compile and run the complete source regression suite:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Launch:

```powershell
.\run_desktop.bat
```

## Windows build and installer

Build the frozen application:

```powershell
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA/JARVIS-OMEGA.exe
```

After installing Inno Setup 6.7.1, build the installer:

```powershell
.\build_installer.ps1
```

The installer script reads the canonical release version automatically. For this candidate the expected filename is:

```text
dist/installer/JARVIS-AI-OMEGA-Setup-8.0.0-rc2.exe
```

`dist/installer/SHA256.txt` is generated as installer digest evidence.

## CI release gate

The workflow covers:

- Linux Python 3.11, 3.12, 3.13 and 3.14 regression;
- Windows Python 3.14.7 regression;
- forced compile/import checks;
- resource-warning enforcement;
- exact constrained Python dependency resolution;
- frozen EXE build;
- first-run/package/TTS-worker software healthchecks;
- release-bundle secret exclusion;
- Inno Setup installer build;
- isolated installer install/uninstall without repository checkout or Python setup;
- shortcut/uninstaller checks;
- per-user data preservation after uninstall;
- post-packaging full regression.

A green workflow is required for the automated release gate. It does **not** prove audible TTS, microphone operation, live OpenRouter/OpenAI inference, real Chrome/Notepad interaction, focus handling, DPI behavior, or other physical workstation behavior.

Repository administrators should also enable branch protection/rulesets with required CI checks before treating a release branch as protected. Repository settings are separate from application source code and are not inferred from a green workflow.

## Exact Windows E2E evidence

Use [Windows E2E Evidence Checklist](docs/WINDOWS-E2E-CHECKLIST.md) for the exact release candidate. It covers:

- startup/shutdown/GUI;
- UIA, keyboard, mouse, screenshot and OCR;
- Chrome, Notepad and focus handling;
- microphone, speech recognition and audible TTS;
- live provider, invalid key, timeout, rate limit and unavailable model;
- allowed/blocked file roots, traversal and secret handling;
- DPI, resolution and window movement;
- disconnect/reconnect/provider failure;
- clean installer first run and real configured AI response.

Never reuse manual/device/live evidence from an older commit after source or packaging changes.

## Self-development safety

Production self-modification is disabled by default:

```env
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
```

The controlled path is intended to remain:

```text
problem/proposal
→ baseline benchmark
→ isolated sandbox/branch
→ generated modification
→ static/security checks
→ unit/integration/regression tests
→ post-change benchmark
→ compare with baseline
→ human approval
→ controlled release
→ post-release verification
→ rollback if necessary
```

A failed security check, failed test, regression, invalid benchmark binding or missing approval must block promotion. AI-generated code is not silently promoted to production.

## Documentation

- [Testing & evaluation](docs/V7-TESTING.md)
- [Windows E2E checklist](docs/WINDOWS-E2E-CHECKLIST.md)
- [Dependency reproduction](docs/DEPENDENCIES.md)
- [Architecture](docs/V7-ARCHITECTURE.md)
- [Agent / missions](docs/V7-AGENT.md)
- [Security](docs/V7-SECURITY.md)
- [Computer use](docs/V7-COMPUTER-USE.md)
- [Self development](docs/V7-SELF-DEVELOPMENT.md)
- [Release guide](docs/V7-RELEASE.md)
- [Troubleshooting](docs/V7-TROUBLESHOOTING.md)

Some documentation filenames retain historical V7/V7.5 naming for compatibility/history. Those labels are not independent application-version authorities; the current application release version is `8.0.0-rc2` from `jarvis.version`.

## Release rule

Do not describe this candidate as fully verified or production-ready while any required automated gate is red or any release claim depends on device/live-service evidence that is still `NOT VERIFIED`.

MIT License — see [LICENSE](LICENSE).
