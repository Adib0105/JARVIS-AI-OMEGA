# JARVIS AI OMEGA 8.0.0-rc1 — Windows Setup

The filename is retained for historical links. Application versioning comes only from `jarvis.version.APP_VERSION`.

## Requirements

Recommended development environment:

- Windows 10/11 64-bit;
- Python 3.11 or newer for source development;
- Python 3.14.7 for exact Windows release-build reproduction;
- Git;
- PowerShell;
- microphone only when voice-input features will be tested;
- Inno Setup 6.7.1 only when building the installer;
- a configured AI provider or explicitly configured local OpenAI-compatible provider.

## 1. Clone and select the branch

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
git fetch origin
git switch v7-development
git pull origin v7-development
```

If the repository already exists, check `git status` before switching/pulling so local work is not overwritten.

## 2. Run the canonical Windows setup

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

The script creates/uses `.venv`, pins pip to 26.2.1, installs runtime and Windows dependencies through `constraints-release.txt`, preserves an existing `.env`, and runs the canonical self-check.

For packaging dependencies too:

```powershell
.\setup_windows.ps1 -IncludeBuildTools
```

## 3. Configure local environment

If setup did not already create `.env`:

```powershell
Copy-Item .env.example .env
```

Never commit `.env` or credentials.

OpenRouter example:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-secret>
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Optional local/OpenAI-compatible development provider:

```env
OFFLINE_DEVELOPMENT_ENABLED=true
LOCAL_MODEL_PROVIDER=openai-compatible
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=<your-local-model>
```

No local model is silently installed.

## 4. Safety defaults

```env
TRUSTED_LOCAL_MODE=true
SELF_DEVELOPMENT_ENABLED=true
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
AUTO_ROLLBACK_ENABLED=false
```

Trusted Local Mode does not bypass high-risk, destructive, credential or protected self-development boundaries.

## 5. Diagnostics and regression

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`self_check_v75.py` is only a backward-compatible wrapper around the canonical release self-check.

Import/package success does not prove microphone, audible TTS, real desktop interaction or live provider inference; those require separate exact-candidate E2E evidence.

## 6. Launch

Desktop:

```powershell
.\run_desktop.bat
```

Direct Python alternative:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Terminal:

```powershell
.\run_jarvis.bat
```

## 7. Build the Windows application

For exact release reproduction, use Python 3.14.7 and constrained dependencies. If build tools were not installed during setup:

```powershell
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt
```

Build:

```powershell
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA/JARVIS-OMEGA.exe
```

The build derives Windows PE version metadata from `jarvis.version`, embeds it via PyInstaller and verifies the actual executable metadata. Private `.env`, runtime databases and OAuth credentials/tokens must not be bundled.

## 8. Build the installer

Install Inno Setup 6.7.1, then run:

```powershell
.\build_installer.ps1
```

Installer definition:

```text
installer/JarvisOmega.iss
```

For 8.0.0-rc1 the expected output is:

```text
dist/installer/JARVIS-AI-OMEGA-Setup-8.0.0-rc1.exe
```

`dist/installer/SHA256.txt` contains installer checksum evidence.

## 9. Real Windows E2E

After source/package tests pass, use [WINDOWS-E2E-CHECKLIST.md](WINDOWS-E2E-CHECKLIST.md) on the exact candidate for real GUI, Chrome/Notepad, UIA/OCR, focus/DPI, keyboard/mouse verification, microphone, audible TTS, live provider and clean-install checks.

Do not upgrade an unperformed check from `NOT VERIFIED` merely because CI is green.

## Updating an existing checkout

```powershell
git switch v7-development
git pull origin v7-development
.\setup_windows.ps1
```

If packaging files/dependencies changed, use `-IncludeBuildTools` and rerun the full release gate.

## Related documents

- [DEPENDENCIES.md](DEPENDENCIES.md)
- [V7-TESTING.md](V7-TESTING.md)
- [V7-RELEASE.md](V7-RELEASE.md)
- [WINDOWS-E2E-CHECKLIST.md](WINDOWS-E2E-CHECKLIST.md)
- [V7-SECURITY.md](V7-SECURITY.md)
- [V7-TROUBLESHOOTING.md](V7-TROUBLESHOOTING.md)
