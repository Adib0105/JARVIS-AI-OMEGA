# JARVIS AI OMEGA V6 — ARC Desktop Agent

> **A multimodal desktop AI agent created by Adib Azam.**

![Version](https://img.shields.io/badge/JARVIS-V6-cyan)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Free Test](https://img.shields.io/badge/OpenRouter-openrouter%2Ffree-purple)
![HUD](https://img.shields.io/badge/UI-Animated%20ARC%20HUD-cyan)
![Images](https://img.shields.io/badge/Vision-Images%20%2B%20Screen-magenta)
![Docs](https://img.shields.io/badge/Documents-PDF%20DOCX%20XLSX%20CSV-orange)
![Voice](https://img.shields.io/badge/Voice-Hindi%20%2F%20Hinglish-green)
![License](https://img.shields.io/badge/License-MIT-green)

**JARVIS AI OMEGA V6** upgrades the project from a chat dashboard into an approval-gated Windows desktop agent. It combines AI chat, multimodal vision, animated ARC-style UI, spoken replies, optional microphone/wake-word input, web research, persistent memory, tasks/reminders, document intelligence, coding workspace tools, browser/app controls, and a Planner → Executor → Reviewer mission mode.

The interface permanently displays **OPERATOR: ADIB AZAM** and the ARC reactor changes animation state while JARVIS is idle, thinking, listening, speaking, or reporting an error.

## V6 highlights

- **Animated ARC reactor HUD** built with Tkinter Canvas
- Speaking/listening/thinking waveform animation
- Dark futuristic Iron-Man-inspired dashboard design
- Typed chat with deep Hindi/Hinglish/English neural spoken replies
- **Push-to-talk microphone** (`Ctrl+M`) using optional Windows audio packages
- Optional runtime **“Hey Jarvis” wake-word listener**
- OpenRouter `openrouter/free` test mode + optional OpenAI mode
- **Mission mode:** Planner → tool-capable Executor → Reviewer
- Multi-step function/tool calling with free-router fallback
- Upload **1–4 images** and ask questions
- Paste image directly from Windows clipboard
- Permission-gated current-screen vision
- Free web/news search and webpage reading
- Persistent SQLite chat sessions and long-term facts
- Search previous local chat history
- Local knowledge base
- **PDF / DOCX / XLSX / XLSM / CSV / TXT / Markdown intelligence**
- Local todos and reminders with spoken reminder alerts in the desktop UI
- Live CPU / RAM / disk / battery / process telemetry
- Allowlisted Windows app launching
- Browser search launch for Google / YouTube / GitHub / Bing
- Approval-gated keyboard typing, hotkeys, key presses, and screen-coordinate clicks
- Safe local file search/read/open
- Guarded coding workspace tree inspection
- Approval-gated text/code file writes with automatic backups
- Allowlisted Python `unittest` project test runner
- Markdown chat export
- GitHub Actions CI across multiple Python versions

## Safety design

V6 is powerful without exposing unrestricted host control. It does **not** provide arbitrary shell execution, credential scraping, password extraction, unrestricted deletion, stealth persistence, security bypasses, or silent software installation.

Sensitive local actions remain permission-gated by default. Secret-like paths such as `.env`, SSH keys, credential folders, tokens, wallets, and password-like files are blocked by the local file layer. Coding writes are limited to approved roots and safe text/code file types, and existing files receive a backup before replacement.

---

# Install / update on Windows

Inside your cloned repository:

```powershell
git pull
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
.\.venv\Scripts\python.exe self_check.py
```

Start the animated desktop version:

```powershell
.\run_desktop.bat
```

or:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Terminal version:

```powershell
.\run_jarvis.bat
```

## Free test configuration

Your `.env` can use:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openrouter/free
```

Never commit `.env` or API keys to GitHub. If a key appears in a public screenshot, revoke it and create a replacement.

---

# ARC desktop controls

### Left control deck

- **NEW CHAT** — fresh conversation session
- **MISSION F2** — Planner → Executor → Reviewer agent mission
- **SCREEN VISION** — permission-gated screen analysis
- **UPLOAD IMAGE** — attach images from disk
- **PASTE IMAGE** — attach copied Windows image
- **BROWSER SEARCH** — approved browser search launch
- **OPEN APP** — approved allowlisted app launcher
- **WAKE WORD** — turn the optional wake listener on/off

### Bottom command deck

- Text box + **SEND**
- **MIC / Ctrl+M** — record a short voice command and send it to JARVIS

### Right intelligence deck

- Active todo list
- Add/complete todos
- Add reminder
- Learn document
- Run project unit tests
- Export chat
- Voice test
- Mute/unmute
- Image help
- Full system status

---

# Image upload and vision

### Upload existing images

1. Open the V6 desktop app.
2. Click **UPLOAD IMAGE** or press `Ctrl+O`.
3. Select up to the configured number of PNG/JPG/JPEG/WEBP images.
4. Type a question such as:

```text
Is screenshot me error kya hai aur exact fix batao.
```

5. Press **SEND**.

You can also leave the prompt empty and press SEND for a general analysis.

### Paste clipboard image

Copy an image/screenshot in Windows, then click **PASTE IMAGE**.

### Screen Vision

Click **SCREEN VISION**. JARVIS asks permission before capturing the current desktop. The image is processed through the same validation/compression pipeline before being sent to the configured AI provider.

Images selected in the app are **not uploaded to GitHub**. They are sent to the configured AI provider only when an analysis request is submitted.

---

# Voice and wake word

V6 still works perfectly as typed-input + spoken-output JARVIS. Microphone input is optional.

Default voice profile:

```env
VOICE_ENGINE=edge
VOICE_HINDI=hi-IN-MadhurNeural
VOICE_HINGLISH=en-IN-PrabhatNeural
VOICE_ENGLISH=en-IN-PrabhatNeural
EDGE_VOICE_RATE=-2%
EDGE_VOICE_VOLUME=+5%
EDGE_VOICE_PITCH=-20Hz
```

Optional microphone settings:

```env
ENABLE_MIC_INPUT=true
ENABLE_WAKE_WORD=false
WAKE_WORD=hey jarvis
SPEECH_LANGUAGE=en-IN
MIC_RECORD_SECONDS=6
```

Wake-word mode never needs to be permanently enabled. You can keep it off and use push-to-talk only.

---

# Documents and local knowledge

V6 can extract approved documents and index their text into its local knowledge base:

- PDF (`pypdf`)
- Word DOCX
- Excel XLSX / XLSM
- CSV
- TXT / Markdown

In the GUI, click **LEARN DOCUMENT**. File access remains restricted to approved roots and requires permission.

---

# Mission mode

Press **F2** or click **MISSION** and give a goal. V6 runs:

```text
Goal
  ↓
Planner (short safe plan)
  ↓
Executor (uses available tools + permission gates)
  ↓
Reviewer (verifies reported outcomes and summarizes blockers/next action)
```

Mission mode does not bypass permission dialogs.

---

# Coding workspace

V6 can help inspect and modify approved code projects through guarded tools:

- inspect project tree
- read safe code/text files
- create/replace safe text/code files with automatic backup
- run only `python -m unittest discover -s tests -v` through the allowlisted test action

There is intentionally no arbitrary shell command tool.

---

# Terminal power commands

| Command | Purpose |
|---|---|
| `/mission <goal>` | Planner → Executor → Reviewer |
| `/mic` | Push-to-talk command |
| `/image "path" | prompt` | Analyze image |
| `/screen [prompt]` | Analyze screen |
| `/document "path"` | Index approved document |
| `/web <query>` | Public web search |
| `/news <query>` | Recent news |
| `/browser google | query` | Open browser search |
| `/app <name>` | Open allowlisted app |
| `/todo <text>` / `/todos` / `/done <id>` | Todos |
| `/remind YYYY-MM-DD HH:MM | text` | Reminder |
| `/remember` / `/recall` | Long-term facts |
| `/search-history <query>` | Search previous chats |
| `/learn <file>` / `/knowledge <query>` | Local knowledge |
| `/metrics` | CPU/RAM/disk/battery |
| `/export` | Export chat |
| `/status` | Full V6 diagnostics |

---

# Project structure

```text
JARVIS-AI-OMEGA/
├── jarvis/
│   ├── attachments.py
│   ├── automation.py
│   ├── coding_tools.py
│   ├── config.py
│   ├── core.py
│   ├── documents.py
│   ├── gui.py
│   ├── hud.py
│   ├── local_files.py
│   ├── memory.py
│   ├── microphone.py
│   ├── permissions.py
│   ├── prompt.py
│   ├── system_tools.py
│   ├── tools.py
│   ├── ui.py
│   ├── vision.py
│   ├── voice.py
│   └── web_tools.py
├── tests/
├── .github/workflows/ci.yml
├── .env.example
├── requirements.txt
├── requirements-windows.txt
├── setup_windows.ps1
├── run_desktop.bat
├── run_jarvis.bat
├── desktop_app.py
├── main.py
└── self_check.py
```

## Creator

**JARVIS AI OMEGA V6 — Created by Adib Azam**

MIT License — see `LICENSE`.
