# JARVIS AI OMEGA V7 — Verified Desktop AI Agent

> **A multimodal, permission-gated, verification-first Windows AI agent created by Adib Azam.**

![Version](https://img.shields.io/badge/JARVIS-V7-cyan)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Branch](https://img.shields.io/badge/Branch-v7--development-purple)
![CI](https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=v7-development&label=V7%20CI)
![Security](https://img.shields.io/badge/Security-Capability%20Gated-red)
![Memory](https://img.shields.io/badge/Memory-Layered%20V7-green)
![Mission](https://img.shields.io/badge/Missions-Persisted%20%2B%20Verified-orange)
![Vision](https://img.shields.io/badge/Vision-Images%20%2B%20Screen-magenta)
![Voice](https://img.shields.io/badge/Voice-Hindi%20%2F%20Hinglish-green)
![License](https://img.shields.io/badge/License-MIT-green)

**JARVIS AI OMEGA V7** is the next engineering generation of the V6 ARC Desktop Agent. V7 keeps the multimodal desktop experience, voice, vision, documents, productivity tools and Iron-Man-inspired HUD, but rebuilds the internals around five core principles:

1. **Provider-neutral AI architecture**
2. **Persisted missions with verification and recovery**
3. **Capability-based security and auditable approvals**
4. **Layered memory with bounded context retrieval**
5. **Semantic computer use that refuses low-confidence guesses**

The permanent operator identity is:

```text
OPERATOR: ADIB AZAM
```

If asked who created JARVIS, the intended creator identity is **Adib Azam**.

> **Development note:** V7 is currently developed on the `v7-development` branch. The existing V6 release remains on `main` while V7 phases are completed, tested and hardened.

---

# V7 Development Status

| Phase | Status | Scope |
|---|---|---|
| Phase 1 — Foundation | ✅ Implemented | Provider abstraction, config validation, typed error taxonomy, compatibility layer |
| Phase 2 — Agent Reliability | ✅ Implemented | Persisted missions, state machine, verification, retry, recovery, replan, pause/resume/cancel |
| Phase 3 — Security | ✅ Implemented | Capability permissions, Approval Center foundations, audit trail, secret protection |
| Phase 4 — Memory & Context | ✅ Implemented | Layered memory, schema migration, backups, hybrid retrieval, bounded context manager |
| Phase 5 — Computer Use | 🔧 Active hardening | Semantic UI targeting, confidence thresholds, browser abstraction, post-action verification |
| Phase 6 — Observability | ⏳ Next | Health dashboard, latency, failures, model/fallback usage, mission analytics |
| Phase 7 — Evaluation | ⏳ Planned | Regression suites, adversarial/security tests, mission evaluation |
| Phase 8 — Product Polish | ⏳ Planned | Final V7 HUD, installer, backup/restore, release workflow |

V7 phases are not marked complete merely because code exists. Each phase must pass regression tests and quality gates before being considered stable.

---

# What makes V7 different from V6

V6 proved that JARVIS could act as a capable multimodal desktop agent. V7 focuses on making those capabilities **trustworthy, recoverable and explainable**.

### V6 style

```text
User → AI → Tool → Result
```

### V7 architecture

```text
User Request
     │
     ▼
Context Manager
     │
     ▼
Provider-Neutral AI Layer
     │
     ▼
Mission Orchestrator
Plan → Execute → Verify → Recover/Replan
     │
     ▼
Capability Permission Gate
     │
     ▼
Tool Runtime + Audit Evidence
     │
     ▼
Memory / UI / Final Response
```

A V7 mission should not claim that an action succeeded merely because a tool call returned. Where possible, the result is independently verified or explicitly marked as only acknowledged/unverified.

---

# Phase 1 — Provider-Neutral AI Foundation

V7 separates AI providers from the core agent runtime.

Current foundation includes:

- Provider-neutral contracts
- OpenRouter support
- OpenAI-compatible provider support
- Model/tool-call normalization
- Typed error taxonomy
- Configuration validation
- Compatibility with the existing `JarvisOmega` public entry point
- Provider-specific failures normalized into internal error categories

Representative failure categories include:

```text
TIMEOUT
RATE_LIMIT
AUTHENTICATION
PROVIDER_ERROR
MODEL_ERROR
VISION_ERROR
PERMISSION_ERROR
TOOL_ERROR
```

This prevents the core agent from becoming tightly coupled to one API vendor.

---

# Phase 2 — Mission State Machine & Recovery

V7 missions are no longer treated as a simple one-shot loop.

A mission can persist:

- Goal
- Plan
- Step number
- Step status
- Tool evidence
- Verification state
- Error category
- Retry count
- Recovery/replan history
- Mission state

Conceptual mission lifecycle:

```text
CREATED
  ↓
PLANNING
  ↓
RUNNING
  ↓
VERIFYING
  ├── VERIFIED → next step
  ├── RETRYABLE FAILURE → retry
  ├── RECOVERABLE FAILURE → replan
  ├── PAUSED → resume later
  ├── CANCELLED
  └── FAILED
  ↓
COMPLETED
```

V7 also includes foundations for:

- Pause
- Resume
- Cancel
- Retry
- Recovery
- Replanning
- Mission persistence across runtime state

Unsafe side effects are not blindly repeated after ambiguous failures.

---

# Phase 3 — Capability Security

V7 replaces broad “safe/unsafe tool” assumptions with explicit **capabilities**.

Examples:

```text
FILE_READ
FILE_WRITE
SCREEN_READ
SCREEN_CONTROL
BROWSER_READ
BROWSER_CONTROL
KEYBOARD_CONTROL
MOUSE_CONTROL
CODE_READ
CODE_WRITE
EMAIL_READ
EMAIL_SEND
CALENDAR_READ
CALENDAR_WRITE
MEMORY_READ
MEMORY_WRITE
```

Tools are assigned:

- Risk level
- Required capabilities
- Side-effect classification
- Human-readable reason

Typical policy:

- Read-only local/system actions can be auto-allowed when policy permits.
- Writes and desktop control require stronger approval.
- Email send and calendar writes are high-risk actions.
- Unknown/unclassified tools default to high risk.

### Audit trail

V7 records security-relevant tool activity including:

- Mission/session reference
- Tool name
- Risk level
- Capabilities
- Approval status
- Execution status
- Verification status
- Latency
- Provider/model metadata where available

Raw secrets should not be stored in the audit log.

---

# Phase 4 — Layered Memory & Context

V7 memory separates different kinds of information instead of treating everything as one flat facts table.

### Working memory

Short-lived context for the current session or mission.

### Episodic memory

What happened previously.

### Semantic memory

Stable facts/preferences JARVIS currently believes it knows.

### Procedural memory

Workflows or strategies that previously worked.

Long-lived V7 memories include metadata such as:

- kind
- stable key
- content
- importance
- confidence
- source
- metadata
- created/updated timestamps
- last verified time
- active/inactive state

**Current user input always has higher authority than stale stored memory.**

### Database migration

V7 uses additive schema migration. Existing V6 memory tables are preserved.

V7 adds schema metadata and new memory/index tables. Before the first pre-V7 migration, an existing database can be backed up into the local backup directory.

### Hybrid retrieval

V7 local retrieval combines signals such as:

1. Exact token overlap
2. BM25-style lexical relevance
3. Sparse hashing-vector similarity
4. Confidence/importance metadata
5. Optional explicitly configured embedding reranking

Embeddings are **not silently enabled**. Memory is not automatically exported to another service.

Detailed memory design: [`docs/V7-MEMORY.md`](docs/V7-MEMORY.md)

---

# Phase 5 — Semantic Computer Use

V7 is moving away from coordinate-first automation toward **semantic UI targeting**.

Primary strategy:

```text
Observe visible UI controls
        ↓
Search by label / control type / context
        ↓
Score candidate targets
        ↓
Check confidence threshold
        ↓
Request permission when required
        ↓
Perform action
        ↓
Collect post-action evidence
```

If confidence is too low, JARVIS should **refuse to guess** rather than click an uncertain target.

Coordinate clicking remains only a last-resort/manual fallback.

### Windows semantic backend

V7 computer-use work includes a Windows UI Automation path using semantic properties such as:

- visible text/name
- control type
- automation ID where available
- enabled/visible state
- bounds

Windows-only automation dependencies remain optional so core text chat is not broken if semantic desktop packages are unavailable.

### Browser abstraction

V7 separates browser intent from low-level mouse coordinates. The browser layer is designed around safer operations such as:

- Open/search
- Read public page content
- Target browser UI semantically where possible
- Verify navigation/action outcome

Sensitive submit/send/purchase/account actions remain approval-gated.

---

# Multimodal Intelligence

V7 preserves and extends the V6 multimodal stack.

### Image upload

Supported workflow:

1. Click **UPLOAD IMAGE** or press `Ctrl+O`.
2. Select PNG/JPG/JPEG/WEBP images.
3. Type your question.
4. Press SEND.

Multiple images can be attached within configured limits.

Before provider submission, images can be locally validated, resized and compressed.

### Clipboard image

Use **PASTE IMAGE** to attach an image currently copied to the Windows clipboard.

### Screen Vision

**SCREEN VISION** captures the current screen only after the relevant permission flow, then sends the processed image to the configured vision-capable AI route.

Images are not committed to GitHub by the application.

---

# Voice & JARVIS Presence

V7 retains the Iron-Man-inspired speaking/listening experience from V6.

Capabilities include:

- Hindi neural speech
- Hinglish / Indian-English neural speech
- Offline `pyttsx3` fallback
- Push-to-talk microphone
- Optional `Hey Jarvis` wake phrase
- Mute/unmute
- Voice test
- ARC/HUD state transitions

Default example:

```env
ENABLE_VOICE_OUTPUT=true
VOICE_ENGINE=edge
VOICE_HINDI=hi-IN-MadhurNeural
VOICE_HINGLISH=en-IN-PrabhatNeural
VOICE_ENGLISH=en-IN-PrabhatNeural
EDGE_VOICE_RATE=-2%
EDGE_VOICE_VOLUME=+5%
EDGE_VOICE_PITCH=-20Hz
```

Optional microphone:

```env
ENABLE_MIC_INPUT=true
ENABLE_WAKE_WORD=false
WAKE_WORD=hey jarvis
SPEECH_LANGUAGE=en-IN
MIC_RECORD_SECONDS=6
```

Wake-word mode can remain disabled while push-to-talk is used.

---

# Iron-Man-inspired ARC Desktop UI

The desktop experience includes:

- Animated ARC reactor
- IDLE / THINKING / LISTENING / SPEAKING / ERROR states
- Animated waveform/activity visualization
- Permanent `OPERATOR: ADIB AZAM`
- Chat console
- Mission controls
- Vision controls
- Image attachments
- Todos/reminders
- Documents
- System telemetry
- Settings/status tools

V7 product-polish work will further add mission evidence, richer approval information, memory management and health/observability views directly into the dashboard.

---

# Documents & Local Knowledge

Approved local files can be extracted/indexed where supported:

- PDF
- DOCX
- XLSX / XLSM
- CSV
- TXT
- Markdown
- Safe source/code text formats

Features include:

- Extract text
- Index local knowledge
- Search relevant chunks
- Use retrieved content in bounded context
- Avoid indiscriminately sending the entire local database to the AI model

Secret-like document content is blocked from persistent indexing where detected.

---

# Productivity

V7 keeps local productivity tools including:

- Todos
- Reminder scheduler
- Notes
- Agenda
- Chat export
- Search chat history
- Search local knowledge

Cloud integrations remain optional.

---

# Optional Gmail + Google Calendar

The repository contains an optional Google Workspace OAuth layer for:

- Gmail search/read workflows
- Gmail send
- Upcoming Calendar events
- Calendar event creation

It is disabled by default.

No Google credentials or OAuth tokens are included in the repository.

Setup packages:

```powershell
.\setup_google.ps1
```

Then configure your own Google Cloud OAuth Desktop client and keep the credential/token files local and excluded from Git.

High-risk actions such as email sending and calendar creation remain permission-gated.

---

# Coding Agent

Within approved local roots, V7 retains coding-assistant abilities such as:

- Inspect project tree
- Read safe text/source files
- Write approved text/source files
- Create backups before replacement where supported
- Run allowlisted Python unittest discovery
- Read Git status
- Read Git diff
- Read recent Git log

There is intentionally **no unrestricted arbitrary shell executor**.

V7 verification logic is designed to inspect evidence after important coding actions instead of assuming success from a tool acknowledgement alone.

---

# Provider Configuration

## Free testing with OpenRouter

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key_here
OPENROUTER_MODEL=openrouter/free
```

Free routing is useful for development/testing, but model quality and capability availability can vary.

## OpenAI-compatible routes

V7 provider abstraction is designed so the agent core is not tied to one provider implementation.

Optional route models:

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

Local fallback is disabled until explicitly configured.

---

# Install / Run V7 Development Branch

> V7 is still under active development. If you only want the stable V6 branch, stay on `main`.

Clone the repository:

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
```

Switch to V7 development:

```powershell
git fetch origin
git switch v7-development
```

If the branch already exists locally:

```powershell
git switch v7-development
git pull
```

Windows setup:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Self-check:

```powershell
.\.venv\Scripts\python.exe self_check.py
```

Expected final label after a properly configured environment:

```text
JARVIS OMEGA V7: READY
```

Launch desktop UI:

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

---

# Security Rules

V7 deliberately avoids exposing unrestricted high-risk primitives.

The project does **not** intentionally provide:

- unrestricted shell execution
- credential/password extraction
- arbitrary secret scraping
- silent destructive file deletion
- stealth persistence
- security bypass tooling
- silent email/calendar writes
- blind low-confidence UI clicking

Important boundaries:

- API keys belong in local `.env` only.
- Never commit `.env`.
- If a key appears in a screenshot or public post, revoke it and create another.
- File operations are constrained to configured/approved roots.
- Side-effecting actions are capability/risk classified.
- Cloud account actions require the user's own OAuth authorization.
- Unknown tools default to high risk.
- Persistent memory/indexing rejects obvious secret-like content.

---

# Verification Philosophy

A core V7 rule is:

> **Do not claim an external action succeeded unless there is evidence supporting that claim.**

Examples:

- File writes can be read back and compared.
- Unit tests can be verified by return code.
- Gmail/Calendar actions can use provider acknowledgements/IDs.
- Desktop actions that cannot yet be independently observed are marked partial/unverified rather than silently reported as fully verified.

This is a central difference between V7 and simpler command assistants.

---

# Testing & CI

GitHub Actions runs compile and unit-test checks against multiple Python versions used by the project development matrix.

The V7 workflow currently targets regression protection for areas including:

- Provider abstraction
- Error classification
- Mission state/recovery
- Permission/security policy
- Audit handling
- Secret blocking
- Memory migration
- Hybrid retrieval
- Context construction
- Computer-use targeting/verification

During active development, a phase may temporarily show a failing CI run while its regression is being fixed. A phase is considered stable only after its quality gate passes.

---

# Planned V7 Work

### Phase 6 — Observability / Health

Planned:

- Health dashboard
- Provider/model status
- Request latency
- Retry counts
- Failure categories
- Tool success/failure metrics
- Mission completion metrics
- Fallback usage
- API usage/cost reporting where reliable data is available

### Phase 7 — Evaluation

Planned:

- End-to-end mission tests
- Security regression tests
- Adversarial prompt/tool tests
- Memory consistency tests
- Computer-use confidence tests
- Recovery/rollback evaluation
- Voice/vision/document regression coverage

### Phase 8 — Product Polish

Planned:

- Final V7 ARC HUD polish
- Mission progress/evidence UI
- Rich Approval Center
- Audit viewer
- Memory inspect/edit/deactivate UI
- Backup/restore controls
- Windows packaging and installer validation
- Final V7 release workflow

### Controlled self-improvement — later V7 work

Any future self-improvement mechanism must remain controlled:

```text
Propose change
   ↓
Sandbox
   ↓
Tests
   ↓
Security checks
   ↓
Evaluation
   ↓
Human approval
   ↓
Deploy
   ↓
Rollback available
```

JARVIS must not be able to silently disable its own permission engine, audit trail, secret protection or rollback controls.

---

# Repository Branch Strategy

```text
main
└── Stable V6 line while V7 is under development

v7-development
└── Active JARVIS OMEGA V7 engineering branch
```

Do not merge V7 into `main` until the required V7 quality gates are green and the desktop application has been tested on Windows.

---

# Documentation

Current V7 engineering documentation includes files such as:

- [`docs/V7-MEMORY.md`](docs/V7-MEMORY.md)
- V7 architecture / migration documentation in the `docs/` directory
- V7 security/computer-use engineering notes as development progresses

The README is the high-level operator/developer overview; detailed internal rules remain in the V7 docs.

---

# Creator

## JARVIS AI OMEGA V7

**Created by Adib Azam**

Built as a Windows-focused multimodal AI agent with an emphasis on **capability, verification, memory, safety, recoverability and a futuristic JARVIS-style user experience**.

MIT License — see [`LICENSE`](LICENSE).
