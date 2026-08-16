# JARVIS AI OMEGA V6 — Operator Guide

**Operator / Creator:** Adib Azam  
**Release:** 6.0.0

## First start after upgrading from V5

```powershell
git pull
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
.\.venv\Scripts\python.exe self_check.py
.\run_desktop.bat
```

The setup script keeps your existing `.env` and installs the new V6 document/telemetry packages plus optional Windows microphone/desktop-automation packages.

## ARC HUD states

- **IDLE** — cyan core rotation
- **THINKING** — gold activity pulse
- **LISTENING** — purple/magenta waveform
- **SPEAKING** — green energy/waveform animation
- **ERROR** — red diagnostic state

The top-right header permanently identifies the configured operator/creator. Default: **Adib Azam**.

## Chat

Type in the bottom command bar and press **SEND** or Enter. JARVIS answers in the center console and, when voice is enabled, speaks the response.

## Push-to-talk

Click **MIC / CTRL+M** or press `Ctrl+M`. V6 records a short microphone sample, transcribes it, sends the recognized text to the AI, then speaks the response.

Relevant `.env` settings:

```env
ENABLE_MIC_INPUT=true
SPEECH_LANGUAGE=en-IN
MIC_RECORD_SECONDS=6
```

## Wake word

Wake word is optional and defaults OFF. Click **WAKE WORD: OFF** to enable it at runtime, or configure automatic start:

```env
ENABLE_WAKE_WORD=true
WAKE_WORD=hey jarvis
```

Keeping wake-word mode off and using push-to-talk is recommended when you do not want continuous microphone listening.

## Mission mode

Press **F2** or click **MISSION**. Give JARVIS a goal. The high-level flow is:

1. Planner creates a short safe plan.
2. Executor works through each step using available tools.
3. Every sensitive local tool still requests permission.
4. Reviewer summarizes what actually completed, blockers, and next action.

Mission mode never bypasses the permission gate.

## Image intelligence

### Upload

Click **UPLOAD IMAGE** or press `Ctrl+O`, select up to the configured attachment limit, type a question, and press SEND.

### Clipboard

Copy an image in Windows and click **PASTE IMAGE**.

### Current screen

Click **SCREEN VISION**. JARVIS asks permission before capture and provider upload.

Do not include API keys, passwords, recovery codes, banking details, or other secrets in images sent to an AI provider.

## Document intelligence

Click **LEARN DOCUMENT** and choose an approved:

- PDF
- DOCX
- XLSX / XLSM
- CSV
- TXT / Markdown

V6 extracts text and indexes it into the local SQLite knowledge store. The file must be inside an approved local root and access remains permission-gated.

## Computer controls

V6 can request approved actions such as:

- open Notepad, Calculator, Explorer, Paint, Task Manager, VS Code, Chrome or Edge
- open an HTTP/HTTPS URL
- launch Google/Bing/YouTube/GitHub searches
- type text into the focused application
- press allowlisted keys/hotkeys
- click a specific screen coordinate
- open an approved local file/folder

These actions are not silent. The default configuration asks you to approve them.

## Coding workspace

V6 can inspect approved project trees, read safe source files, write safe text/code files, and run the allowlisted Python `unittest` action.

When V6 replaces an existing source/text file through its guarded write tool, it creates a timestamped backup first.

There is no unrestricted shell command executor.

## Todos and reminders

Use the right-side task panel to add/complete todos and create local reminders. While the desktop app is running, due reminders appear in the chat, trigger a system bell, and are spoken when voice output is enabled.

Terminal commands are also available:

```text
/todo Finish project
/todos
/done 1
/remind 2026-08-16 18:30 | Check JARVIS build
/reminders
```

## Settings panel

Click **SETTINGS**. The panel can edit non-secret options such as:

- voice on/off, pitch/rate/volume
- push-to-talk and wake-word options
- approval-gate setting
- desktop/document/coding feature toggles
- mission step limit
- telemetry/reminder refresh settings

API keys are deliberately hidden and cannot be edited through this panel. Changes are written to `.env` and apply after restart.

The same panel also opens logs and crash-report folders.

## Logs and crash reports

Local runtime log:

```text
data/logs/jarvis-v6.log
```

Unhandled crash reports:

```text
data/crash-reports/
```

These folders are excluded from Git by the existing `data/` ignore rule.

## Update checker

Click **CHECK UPDATE** or run:

```powershell
.\.venv\Scripts\python.exe check_update.py
```

The checker only checks the repository's latest GitHub Release and offers its page. It does not silently replace files.

## Build a Windows EXE

```powershell
.\build_windows.ps1
```

The PyInstaller build output is placed under:

```text
dist/JARVIS-OMEGA-V6/
```

API keys are intentionally not bundled. Configure a `.env` alongside the built executable.

## Build a Windows installer

After building the EXE, install Inno Setup 6 and run:

```powershell
.\build_installer.ps1
```

The installer definition can create Start Menu and optional desktop shortcuts.

## What V6 intentionally does not do

For safety, V6 does not provide unrestricted shell execution, credential/password extraction, arbitrary file deletion, stealth persistence, security bypass tools, or silent software installation.

Cloud account integrations such as Gmail/Google Calendar require the user's own OAuth application credentials and consent flow and are therefore not hard-coded into the public repository. A future integration can be added without weakening the local permission model.

A local offline LLM backend is also optional future work; the current free-testing path is OpenRouter and the optional premium path is OpenAI.
