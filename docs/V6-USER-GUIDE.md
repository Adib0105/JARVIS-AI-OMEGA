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

The setup script keeps your existing `.env` and installs V6 document/telemetry packages plus optional Windows microphone/desktop-automation packages.

## ARC HUD states

- **IDLE** — cyan core rotation
- **THINKING** — gold activity pulse
- **LISTENING** — purple/magenta waveform
- **SPEAKING** — green energy/waveform animation
- **ERROR** — red diagnostic state

The top-right header permanently identifies the configured operator/creator. Default: **Adib Azam**.

## Chat

Type in the bottom command bar and press **SEND** or Enter. JARVIS answers in the center console and, when voice is enabled, speaks the response.

## Push-to-talk / wake word

Click **MIC / CTRL+M** or press `Ctrl+M`. V6 records a short microphone sample, transcribes it, sends the recognized text to the AI, then speaks the response.

```env
ENABLE_MIC_INPUT=true
SPEECH_LANGUAGE=en-IN
MIC_RECORD_SECONDS=6
ENABLE_WAKE_WORD=false
WAKE_WORD=hey jarvis
```

Wake-word mode is optional and can remain off while push-to-talk stays available.

## Mission mode

Press **F2** or click **MISSION**. V6 uses:

1. Planner — creates a short safe high-level plan.
2. Executor — works through steps using available tools.
3. Permission Gate — remains active on sensitive local/cloud actions.
4. Reviewer — summarizes confirmed outcomes, blockers, and next action.

Mission mode never bypasses permissions.

## Model routing and optional local fallback

V6 can route requests between configured fast/smart/vision model names. Blank route-model values simply reuse your main provider model:

```env
MODEL_ROUTING=auto
FAST_MODEL=
SMART_MODEL=
VISION_MODEL=
```

You may also point V6 at a local **OpenAI-compatible** server as a fallback. This is disabled unless you explicitly configure a local model:

```env
ENABLE_LOCAL_FALLBACK=false
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=
LOCAL_AI_API_KEY=local
```

The fallback is not a hidden cloud service: you must run/configure the compatible local server yourself. Local fallback chat does not receive the desktop tool registry.

## Memory, notes, summaries and local relevance search

V6 stores chat sessions, non-secret facts, notes, todos, reminders, document chunks, and optional conversation continuity summaries in local SQLite storage.

- `search_knowledge` — exact/keyword-oriented search.
- `vector_search_knowledge` — lightweight local sparse hashing-vector relevance search; it does **not** call an external embedding API.
- Session summaries are off by default and can be enabled with:

```env
AUTO_SUMMARIZE=false
SUMMARIZE_AFTER_MESSAGES=60
```

Never store API keys, passwords, recovery codes, banking secrets, or other sensitive credentials as JARVIS notes/facts.

## Image intelligence

- **UPLOAD IMAGE / Ctrl+O** — select existing PNG/JPG/JPEG/WEBP files.
- **PASTE IMAGE** — attach an image copied to the Windows clipboard.
- **SCREEN VISION** — current desktop capture only after permission.

After attaching an image, type your question and press SEND. Do not send API keys, passwords, recovery codes, banking details, or other secrets in screenshots.

## Document intelligence

Click **LEARN DOCUMENT** and choose an approved:

- PDF
- DOCX
- XLSX / XLSM
- CSV
- TXT / Markdown

V6 extracts text and indexes it into local knowledge. The document must be inside an approved local root and access remains permission-gated.

## Computer controls

V6 can request approved actions such as:

- open Notepad, Calculator, Explorer, Paint, Task Manager, VS Code, Chrome or Edge
- open an HTTP/HTTPS URL
- launch Google/Bing/YouTube/GitHub searches
- type text into the focused application
- press allowlisted keys/hotkeys
- click a specific screen coordinate
- open an approved local file/folder

PyAutoGUI fail-safe remains enabled. These actions are not silent: the default configuration asks you to approve them.

## Coding workspace + Git diagnostics

V6 can inspect approved project trees, read safe source files, write safe text/code files, and run allowlisted Python `unittest` discovery. Existing files receive a timestamped backup before guarded replacement.

Read-only Git diagnostics are also available through the AI tool layer:

- `git_status`
- `git_diff`
- `git_log`

Git tools do not commit, push, reset, delete, or modify repository history. There is intentionally no unrestricted shell command executor.

## Todos, reminders and agenda

The desktop panel can add/complete todos and create reminders. While the desktop app is running, due reminders appear in chat, trigger a system bell, and are spoken when voice output is enabled.

JARVIS also exposes an agenda tool combining open todos, pending reminders, and recent notes.

## Optional Gmail + Google Calendar

Google integration is **disabled by default** and contains no bundled credentials.

First run:

```powershell
.\setup_google.ps1
```

Then in Google Cloud:

1. Enable **Gmail API** and **Google Calendar API**.
2. Configure the OAuth consent screen.
3. Create an OAuth client with application type **Desktop app**.
4. Download the OAuth JSON and save it in the JARVIS repository as:

```text
google_credentials.json
```

5. Set:

```env
ENABLE_GOOGLE_WORKSPACE=true
```

6. Restart JARVIS. The first approved Gmail/Calendar action opens the browser OAuth consent flow.

The local OAuth token is stored under:

```text
data/google_token.json
```

and `data/` is excluded from Git. If Google OAuth scopes are changed later, remove the saved token and authorize again.

Available agent actions after setup:

- search Gmail messages
- send Gmail messages
- list upcoming primary-calendar events
- create primary-calendar events

**All Google account actions are approval-gated, including reads.**

## Settings panel

Click **SETTINGS**. It can edit non-secret V6 options including:

- voice, mic, wake word
- approval gates
- desktop/document/coding/Google feature toggles
- model routing
- optional local fallback URL/model
- auto conversation summaries
- mission step limit
- telemetry/reminder refresh settings

API keys and OAuth secrets are deliberately hidden and cannot be edited through this panel. Changes apply after restart.

## Logs and crash reports

Local runtime log:

```text
data/logs/jarvis-v6.log
```

Unhandled crash reports:

```text
data/crash-reports/
```

The Settings panel can open both folders.

## Update checker

Click **CHECK UPDATE** or run:

```powershell
.\.venv\Scripts\python.exe check_update.py
```

The checker only checks the repository's latest GitHub Release and offers its page. It does not silently replace files.

## Build a Windows EXE / installer

Build PyInstaller folder:

```powershell
.\build_windows.ps1
```

Output:

```text
dist/JARVIS-OMEGA-V6/
```

API keys are intentionally not bundled. Configure `.env` alongside the built executable.

After installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

The installer definition supports Start Menu and optional desktop shortcuts.

## What V6 intentionally does not do

For safety, V6 does not provide unrestricted shell execution, credential/password extraction, arbitrary file deletion, stealth persistence, security bypass tools, or silent software installation. Cloud actions require explicit account authorization and remain approval-gated.
