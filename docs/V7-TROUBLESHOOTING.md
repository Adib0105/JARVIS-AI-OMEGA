# JARVIS AI OMEGA — Troubleshooting

The filename is historical. Use this guide for the current `v7-development` release candidate; the application version is defined by `jarvis.version.APP_VERSION`.

## First diagnostic commands

```powershell
git status
git branch --show-current
git pull origin v7-development
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_release.py
```

`self_check_v75.py` is retained only as a backward-compatible wrapper.

For test failures:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## PowerShell command is being sent to JARVIS chat

If you see a `YOU:` prompt, you are inside the JARVIS terminal/chat loop. Exit it before running shell commands:

```text
/exit
```

or press `Ctrl+C`.

## Virtual environment not found

If `.venv\Scripts\python.exe` does not exist:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Source development requires Python 3.11 or newer. Exact Windows release-build reproduction uses Python 3.14.7.

## Missing Python package

Prefer the canonical setup script because it applies the checked-in release constraints:

```powershell
.\setup_windows.ps1
```

Equivalent constrained runtime/Windows commands:

```powershell
.\.venv\Scripts\python.exe -m pip install pip==26.2.1
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-windows.txt
```

For packaging tools:

```powershell
.\setup_windows.ps1 -IncludeBuildTools
```

Do not fix release dependency errors by silently switching to unconstrained upgrades.

## AI provider/configuration error

Check `.env` and verify that the selected provider has the required configuration. Do not paste API keys into screenshots, issues or logs.

OpenRouter example:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<secret>
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

If a key has been exposed publicly, revoke it and create a new one.

Provider configuration is not live-provider verification. Final release readiness requires an actual successful provider response on the exact candidate plus the other required external evidence.

## Google Workspace setup fails

Install the optional pinned Google integration dependencies through the dedicated script:

```powershell
.\setup_google.ps1
```

This uses `requirements-google.txt` with `constraints-release.txt` and verifies imports. OAuth consent and real Gmail/Calendar operations are separate live checks. Never commit `google_credentials.json` or OAuth tokens.

## Voice continues after closing the app

The current runtime tracks active playback and should terminate it during shutdown. First update the branch and retest:

```powershell
git pull origin v7-development
.\run_desktop.bat
```

Use `Esc` or the STOP button to cancel current speech. If background playback still survives app exit, capture safe/redacted terminal output and the voice-engine configuration without including secrets.

## Voice Player controls are not visible

Fully restart the desktop process after pulling changes. Historical V7/V7.5 labels in old screenshots/docs are not evidence that the running build is current.

## Approval Center appears for `open chrome`

With `TRUSTED_LOCAL_MODE=true`, ordinary allowlisted LOW/MEDIUM local actions such as opening Chrome should not require repetitive approval.

```env
TRUSTED_LOCAL_MODE=true
```

High-risk keyboard/mouse control, file/code writes, email send and calendar writes remain capability-gated.

## Computer-use target not found

Computer Use intentionally stops rather than guessing.

```text
UI Automation → confidence/ambiguity gate → optional OCR fallback → action → observation → verification
```

If UIA returns an ambiguous result, OCR must not bypass it. If OCR dependencies are unavailable or confidence is insufficient, JARVIS should report degraded/partial/unverified behavior rather than clicking guessed coordinates.

## Screen Vision does not work

Verify Windows screen-capture/display conditions and that the target is not hidden behind a modal dialog. A package/import check does not prove the real screen path. Use the Command Center plus the real Windows checklist for actual device evidence.

## Windows SQLite `WinError 32`

Current storage uses deterministic connection cleanup. If a new lock appears:

1. pull the latest branch;
2. reproduce with the full test suite;
3. identify the exact `.db` file and test name;
4. fix the leaked lifecycle/resource root cause;
5. do not hide the problem by deleting tests or adding arbitrary sleeps.

## Test says `VERIFIED` when evidence is partial

Verification is evidence-based. Tool-call success alone must not be converted into real-world success. Computer-use operations can remain `PARTIAL`, `FAILED` or `UNVERIFIED` when the expected result cannot be independently observed.

## Browser page blocked

Browser security intentionally rejects or treats cautiously:

- non-HTTP/HTTPS schemes;
- embedded URL credentials;
- localhost/private/link-local/reserved targets in public-reader paths;
- page content that tries to override instructions, reveal secrets or bypass security.

Webpage text is untrusted data, not policy.

## Self-development proposal cannot deploy

That is expected unless every controlled-release gate is satisfied. `APPROVED` is not `DEPLOYED`.

Safe defaults:

```env
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
```

Release additionally requires the enforced policy/security checks, reviewed source state, clean production checkout, expected HEAD match, fresh tests and fast-forward-only deployment.

## Local/offline model unavailable

Offline development is optional. JARVIS does not silently install a model. Configure an OpenAI-compatible local runtime deliberately and verify that local server/model separately.

## Windows EXE build fails

Use the constrained packaging setup, then build:

```powershell
.\setup_windows.ps1 -IncludeBuildTools
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA/JARVIS-OMEGA.exe
```

The build must generate canonical PE metadata, verify the actual EXE file/product version, run packaged software healthchecks and reject bundled private runtime data. A missing EXE, metadata mismatch, failed healthcheck or secret-bundle validation is fatal.

## EXE metadata mismatch

Do not edit a second version string to make the check pass. Verify:

```powershell
.\.venv\Scripts\python.exe -c "from jarvis.version import APP_VERSION, WINDOWS_FILE_VERSION; print(APP_VERSION, WINDOWS_FILE_VERSION)"
```

Then rebuild with `build_windows.ps1`. The canonical application version and derived Windows numeric version must match the actual frozen executable metadata.

## Chat remains in THINKING

`AI_TIMEOUT_SECONDS` is the wall-clock budget for one normal chat request, including retries, provider/tool continuations, quality repair and local fallback. Use the visible CANCEL control to interrupt the request. Timeout/cancellation must restore a terminal UI state rather than leaving THINKING active.

For explicit multi-step missions use `MISSION_TIMEOUT_SECONDS`; vision uses `VISION_TIMEOUT_SECONDS`.

## Text appears but voice is silent

Software TTS worker health is not proof of audible playback. Check the configured voice/fallback, TTS deadlines, Windows output device and safe/redacted `tts_*` events. Packaged TTS workers must not open a second JARVIS window.

Then perform the audible-speaker item in `WINDOWS-E2E-CHECKLIST.md` on the exact package. Keep the status `NOT VERIFIED` until sound is actually heard.

## Microphone dependency is installed but speech does not work

Importability is not a physical microphone test. Confirm the Windows input device/privacy permissions, then run the microphone/speech items in `WINDOWS-E2E-CHECKLIST.md`. Do not mark them verified from dependency presence alone.

## Inno Setup installer cannot build

The release baseline uses Inno Setup 6.7.1. After `build_windows.ps1` succeeds:

```powershell
.\build_installer.ps1
```

The installer version is read from `jarvis.version`; callers should not supply a second release version.

## CI is green but release still says NOT VERIFIED

That can be correct. CI proves the automated gates for the exact commit; it does not physically hear audio, speak into a microphone, operate your real Chrome/Notepad windows, validate your display DPI/focus conditions or make a live provider account successful.

Use `WINDOWS-E2E-CHECKLIST.md` and bind the evidence to the exact candidate. Never reuse external evidence after the candidate changes.

## Before reporting a bug

Include:

- Windows version;
- Python version;
- exact branch and commit SHA;
- whether the issue is source, frozen EXE or installed build;
- exact command/feature used;
- expected result;
- actual result;
- safe/redacted error text or screenshot;
- relevant `self_check.py` / `self_check_release.py` output.

Never include `.env`, passwords, API keys, OAuth tokens, private credentials or live private databases.
