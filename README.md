# JARVIS AI OMEGA V6 — ARC Desktop Agent

> **A multimodal, permission-gated Windows AI agent created by Adib Azam.**

![Version](https://img.shields.io/badge/JARVIS-V6-cyan)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CI](https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=main&label=CI)
![Free Test](https://img.shields.io/badge/OpenRouter-openrouter%2Ffree-purple)
![HUD](https://img.shields.io/badge/UI-Animated%20ARC%20HUD-cyan)
![Vision](https://img.shields.io/badge/Vision-Images%20%2B%20Screen-magenta)
![Docs](https://img.shields.io/badge/Documents-PDF%20DOCX%20XLSX%20CSV-orange)
![Voice](https://img.shields.io/badge/Voice-Hindi%20%2F%20Hinglish-green)
![License](https://img.shields.io/badge/License-MIT-green)

JARVIS AI OMEGA V6 turns the project into a real desktop-agent platform: **typed chat, spoken replies, optional microphone/wake word, animated ARC-style HUD, images and screen vision, web research, memory, notes, tasks/reminders, documents, coding/Git diagnostics, safe computer controls, optional Gmail/Calendar OAuth, model routing, and Planner → Executor → Reviewer missions**.

The main dashboard permanently shows **OPERATOR: ADIB AZAM**. The ARC core visibly changes state while JARVIS is **IDLE, THINKING, LISTENING, SPEAKING, or reporting an ERROR**.

## What V6 can do

### AI brain

- OpenRouter `openrouter/free` testing mode by default
- Optional OpenAI provider mode
- Multi-step function/tool calling with free-router fallback
- Fast / smart / vision model routing configuration
- Optional local OpenAI-compatible model fallback
- Planner → Executor → Reviewer **Mission mode**
- High-level mission progress without exposing private chain-of-thought

### Iron-Man-inspired desktop UX

- Animated Tkinter ARC reactor
- Rotating HUD rings and energy spokes
- Thinking/listening/speaking/error visual states
- Animated waveform while JARVIS is active
- Live CPU, RAM, disk, battery, process and network telemetry
- Dark futuristic three-panel command dashboard
- Permanent operator/creator identity
- In-app Settings, Update Check, logs and crash-report access

### Voice

- Deep Indian neural voice via Edge TTS
- Automatic Hindi / Hinglish / English speech selection
- Offline `pyttsx3` fallback
- Push-to-talk microphone (`Ctrl+M`)
- Optional runtime **Hey Jarvis** wake-word listener
- Voice mute/unmute and test

### Vision

- Upload up to 1–4 images per request
- Paste an image from the Windows clipboard
- Local image preview, validation, resize and compression
- Permission-gated current-screen capture and AI analysis
- Friendly vision timeout / unsupported-model errors

### Web + knowledge

- Free public web search and news search
- Webpage text extraction
- Persistent SQLite sessions and facts
- Search previous chat history
- Local notes and agenda
- Local knowledge indexing
- Keyword knowledge search
- Lightweight local sparse-vector relevance search without an embeddings API
- Optional conversation continuity summaries

### Documents

Approved local files can be extracted/indexed:

- PDF
- DOCX
- XLSX / XLSM
- CSV
- TXT / Markdown

### Productivity

- Todos
- Reminder scheduler
- Spoken reminder alerts while the desktop app is running
- Agenda combining tasks, reminders and notes
- Markdown chat export

### Desktop agent

All sensitive actions remain permission-gated by default:

- Open allowlisted Windows apps
- Open approved URLs and local paths
- Launch Google / Bing / YouTube / GitHub searches
- Type text into the focused app
- Press allowlisted keys and hotkeys
- Click approved visible screen coordinates
- Search/read approved local files

PyAutoGUI fail-safe remains enabled.

### Coding agent

- Inspect approved project tree
- Read safe source/text files
- Write approved source/text files with automatic timestamped backup
- Run only allowlisted Python `unittest` discovery
- Read-only Git status, diff and recent log

There is intentionally **no arbitrary shell executor**.

### Optional Gmail + Google Calendar

The repository includes an optional OAuth integration layer for:

- Gmail search
- Gmail send
- Upcoming primary-calendar events
- Calendar event creation

It is **disabled by default**. No Google credentials or tokens are included. Every Google account action, including reads, remains approval-gated.

---

# Quick update / install

Inside the cloned repository:

```powershell
git pull
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
.\.venv\Scripts\python.exe self_check.py
```

Start the ARC desktop dashboard:

```powershell
.\run_desktop.bat
```

or:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Terminal mode:

```powershell
.\run_jarvis.bat
```

## Free testing `.env`

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openrouter/free
```

Never commit `.env` or an API key. If a key appears in a screenshot or public post, revoke it and create a replacement.

---

# ARC desktop controls

**Left:** ARC core, live telemetry, New Chat, Mission, Screen Vision, Upload/Paste Image, Browser Search, Open App, Wake Word.  
**Center:** image attachment strip + JARVIS conversation console.  
**Bottom:** command input, SEND, MIC / Ctrl+M.  
**Right:** todos/reminders, document learning, code tests, export, voice controls, status, settings, update check.

Keyboard shortcuts:

```text
Enter      Send
Ctrl+O     Upload image
Ctrl+M     Push-to-talk
Ctrl+L     Focus command input
F2         Mission mode
```

---

# Image / Screen Vision

1. Click **UPLOAD IMAGE** or press `Ctrl+O`.
2. Select PNG/JPG/JPEG/WEBP images.
3. Type a question.
4. Press SEND.

**PASTE IMAGE** reads an image currently copied to the Windows clipboard. **SCREEN VISION** asks permission before current-screen capture.

Selected images are not uploaded to GitHub. When you submit an analysis request, the processed image is sent to your configured AI provider.

---

# Voice configuration

```env
ENABLE_VOICE_OUTPUT=true
VOICE_ENGINE=edge
VOICE_HINDI=hi-IN-MadhurNeural
VOICE_HINGLISH=en-IN-PrabhatNeural
VOICE_ENGLISH=en-IN-PrabhatNeural
EDGE_VOICE_RATE=-2%
EDGE_VOICE_VOLUME=+5%
EDGE_VOICE_PITCH=-20Hz

ENABLE_MIC_INPUT=true
ENABLE_WAKE_WORD=false
WAKE_WORD=hey jarvis
SPEECH_LANGUAGE=en-IN
MIC_RECORD_SECONDS=6
```

Wake-word mode can stay OFF while push-to-talk remains available.

---

# Model routing + local fallback

Blank route-model values reuse the main provider model:

```env
MODEL_ROUTING=auto
FAST_MODEL=
SMART_MODEL=
VISION_MODEL=
```

Optional local OpenAI-compatible fallback:

```env
ENABLE_LOCAL_FALLBACK=false
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=
LOCAL_AI_API_KEY=local
```

The user must run/configure the compatible local server and model separately. Local fallback is disabled until explicitly configured.

---

# Google Workspace setup

First install optional Google packages:

```powershell
.\setup_google.ps1
```

Then enable Gmail API + Google Calendar API in your own Google Cloud project, create an **OAuth Desktop app**, and save the downloaded client JSON locally as:

```text
google_credentials.json
```

Enable it:

```env
ENABLE_GOOGLE_WORKSPACE=true
```

The first approved Gmail/Calendar action opens the browser consent flow. The resulting local token is stored under `data/google_token.json`, which is excluded from Git.

---

# Windows application packaging

Create a PyInstaller desktop build:

```powershell
.\build_windows.ps1
```

Then, after installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

API keys are intentionally **not bundled** into builds.

---

# Safety model

V6 deliberately does **not** expose:

- unrestricted shell execution
- credential/password extraction
- secret-file scraping
- arbitrary file deletion
- silent software installation
- stealth persistence
- security-bypass tools

Secret-like paths are blocked. Local writes are restricted to approved roots and safe text/code types, with backups on replacement. Cloud account actions require user-owned OAuth authorization and explicit approval.

---

# Core architecture

```text
                         JARVIS OMEGA V6
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
              ARC UI                     AI Router
       IDLE/THINK/LISTEN/SPEAK                │
                 │               ┌───────────┼───────────┐
                 │             Fast        Smart       Vision
                 │                           │
                 └─────────────── Agent Core ─────────────┘
                                   │
                     Planner → Executor → Reviewer
                                   │
       ┌─────────┬─────────┬───────┼────────┬─────────┬──────────┐
      Vision     Web      Memory   Docs    Desktop    Coding    Google*
       │          │         │       │         │          │         │
   Images/     Search/    Notes/  PDF/     Approval   Tests/    Gmail/
   Screen       News      Tasks   Office     Gate      Git      Calendar

* Optional and disabled until user OAuth setup.
```

## Documentation

See [`docs/V6-USER-GUIDE.md`](docs/V6-USER-GUIDE.md) for the detailed operator guide.

## Creator

**JARVIS AI OMEGA V6 — Created by Adib Azam**

MIT License — see `LICENSE`.
