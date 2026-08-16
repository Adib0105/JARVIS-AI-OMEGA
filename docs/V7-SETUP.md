# JARVIS AI OMEGA V7.5 — Setup Guide

This guide covers a clean Windows development setup for the `v7-development` branch.

## Requirements

Recommended:

- Windows 10/11 64-bit
- Python 3.11–3.14
- Git
- PowerShell
- microphone for voice input (optional)
- Inno Setup 6 only if you want to compile the installer
- a configured AI provider, or an explicitly configured local OpenAI-compatible model

## 1. Clone and select the development branch

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
git fetch origin
git switch v7-development
git pull origin v7-development
```

If the repository already exists:

```powershell
git status
git switch v7-development
git pull origin v7-development
```

Do not overwrite local work before checking `git status`.

## 2. Run Windows setup

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

The project virtual environment is expected at `.venv`.

## 3. Configure environment variables

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`.

### OpenRouter example

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-secret>
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### Optional OpenAI-compatible/local provider

```env
OFFLINE_DEVELOPMENT_ENABLED=true
LOCAL_MODEL_PROVIDER=openai-compatible
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=<your-local-model>
```

No local model is silently installed by JARVIS.

## 4. Recommended safety defaults

```env
TRUSTED_LOCAL_MODE=true
SELF_DEVELOPMENT_ENABLED=true
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
AUTO_ROLLBACK_ENABLED=false
```

Trusted Local Mode reduces repetitive approval prompts for ordinary allowlisted local actions. It does not grant unrestricted shell, credential or destructive access.

## 5. Run diagnostics

Basic check:

```powershell
.\.venv\Scripts\python.exe self_check.py
```

V7.5 engineering check:

```powershell
.\.venv\Scripts\python.exe self_check_v75.py
```

Full compile and regression suite:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 6. Launch desktop JARVIS

Preferred:

```powershell
.\run_desktop.bat
```

Alternative:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Open the Agent Command Center with:

```text
Ctrl + Shift + C
```

## 7. Voice controls

The desktop voice strip provides:

```text
- SPEED | PLAY / PAUSE | STOP | SPEED +
```

Shortcuts:

```text
Esc           stop speech
Ctrl + Space  play/pause
Ctrl + -      slower
Ctrl + +      faster
```

Closing the app should terminate active playback.

## 8. Computer-use validation

Recommended first commands:

```text
open chrome
open calculator
browser me Python search karo
```

Computer Use V2 resolves semantic UI Automation targets first. OCR is an optional local fallback and should never be used to bypass an ambiguous UIA result.

## 9. Optional Google Workspace

Google integrations are optional. Configure OAuth only if Gmail/Calendar features are required. Keep credentials and generated tokens private and outside commits.

## 10. Build the Windows application

Install build dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Build:

```powershell
.\build_windows.ps1
```

Expected application path:

```text
dist/JARVIS-OMEGA-V7/JARVIS-OMEGA-V7.exe
```

Private `.env`, live SQLite databases and Google OAuth credentials/tokens must not be bundled.

## 11. Build the installer

After installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

Installer definition:

```text
installer/JARVIS-OMEGA-V7.iss
```

## Update workflow

Before testing a new development revision:

```powershell
git switch v7-development
git pull origin v7-development
.\.venv\Scripts\python.exe self_check_v75.py
```

If dependencies changed, rerun `setup_windows.ps1` or install the updated requirements explicitly.

## Next documents

- [V7-TROUBLESHOOTING.md](V7-TROUBLESHOOTING.md)
- [V7-TESTING.md](V7-TESTING.md)
- [V7-SECURITY.md](V7-SECURITY.md)
- [V7.5-STATUS.md](V7.5-STATUS.md)
