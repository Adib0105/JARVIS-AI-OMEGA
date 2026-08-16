# JARVIS AI OMEGA V7.5 — Troubleshooting

Use this guide after pulling the latest `v7-development` branch.

## First diagnostic commands

```powershell
git status
git branch --show-current
git pull origin v7-development
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
```

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

## Missing Python package

Use the project interpreter, not a random global Python installation:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For packaging:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

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

## Voice continues after closing the app

V7 tracks active playback and should terminate it during shutdown. First update the branch and retest:

```powershell
git pull origin v7-development
.\run_desktop.bat
```

Use `Esc` or the STOP button to cancel current speech. If background playback still survives app exit, capture the terminal output and the exact voice engine configuration without including secrets.

## Voice Player controls are not visible

The V7 voice strip is designed to remain visible above the input area. Make sure the latest branch is loaded and fully restart the desktop process after pulling changes.

## Approval Center appears for `open chrome`

With `TRUSTED_LOCAL_MODE=true`, ordinary allowlisted LOW/MEDIUM local actions such as opening Chrome should not require repetitive approval.

Check:

```env
TRUSTED_LOCAL_MODE=true
```

High-risk keyboard/mouse control, file/code writes, email send and calendar writes remain capability-gated.

## Computer-use target not found

Computer Use V2 intentionally stops rather than guessing.

Resolution order:

```text
UI Automation → confidence/ambiguity gate → optional OCR fallback → action → evidence
```

If UIA returns an ambiguous result, OCR must not bypass it. If OCR dependencies are unavailable, JARVIS should report degraded/unavailable behavior instead of clicking guessed coordinates.

## Screen Vision does not work

Verify that screen-capture permission is granted by Windows and that the app is not blocked behind another modal dialog. Run the Health/Capability views in the Agent Command Center to see whether vision/screen capture is AVAILABLE, DEGRADED or DISABLED.

## Windows SQLite `WinError 32`

Current V7 storage uses deterministic connection cleanup. If a new lock appears:

1. pull the latest branch;
2. reproduce with the full test suite;
3. identify the exact `.db` file and test name;
4. do not work around it by deleting tests or adding sleeps.

## Test says `VERIFIED` when evidence is partial

Verification is evidence-based. Tool success alone must not be converted into real-world success. Computer-use actions can return `PARTIAL`, `FAILED` or `UNVERIFIED` when independent observation is unavailable.

## Browser page blocked

Browser V2 intentionally rejects or treats cautiously:

- non-HTTP/HTTPS schemes
- embedded URL credentials
- localhost/private/link-local/reserved literal targets in public-reader paths
- page content that tries to override instructions, reveal secrets or bypass security

Webpage text is untrusted data, not policy.

## Self-development proposal cannot deploy

That is expected unless every release gate is satisfied. `APPROVED` is not `DEPLOYED`.

Safe defaults:

```env
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
```

The release path additionally requires a clean production checkout, expected HEAD match, fresh tests, policy/security pass and fast-forward-only deployment.

## Local/offline model unavailable

Offline development is optional. JARVIS does not silently install a model. Configure an OpenAI-compatible local runtime deliberately, then verify the local server/model separately.

## Windows EXE build fails

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_windows.ps1
```

The CI package smoke build is the reference gate. A local warning is not automatically fatal; a missing executable or bundled private runtime data is fatal.

## Inno Setup installer cannot build

Install Inno Setup 6, then run:

```powershell
.\build_installer.ps1
```

## Before reporting a bug

Include:

- Windows version
- Python version
- branch and commit SHA
- exact command/feature used
- expected result
- actual result
- safe error text or screenshot
- relevant `self_check_v75.py` output

Never include `.env`, passwords, API keys, OAuth tokens or private credentials.
