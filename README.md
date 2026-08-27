# JARVIS AI OMEGA V7.5 — Reliable ARC Desktop Agent

<p align="center">
  <strong>Multimodal • Evidence-Driven • Capability-Aware • Windows-First AI Agent</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/JARVIS-V7.5-00d9ff">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11--3.14-3776ab">
  <img alt="Branch" src="https://img.shields.io/badge/Branch-main-2ea44f">
  <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=main&label=CI">
  <img alt="Security" src="https://img.shields.io/badge/Security-Capability%20Gated-dc3545">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-2ea44f">
</p>

<p align="center">
  <strong>Created by Adib Azam</strong><br>
  <code>OPERATOR: ADIB AZAM</code>
</p>

---

JARVIS AI OMEGA V7.5 is a Windows-first multimodal desktop AI agent designed around a strict runtime loop:

```text
UNDERSTAND → PLAN → PERMISSION → EXECUTE → VERIFY → RECOVER / REPLAN
```

It combines typed chat, voice, screen/image vision, local documents, memory/RAG, browser research, Windows computer use, coding/Git tools, productivity workflows, observability, evaluation and controlled self-development.

> **Current branch strategy:** `main` now contains the promoted V7/V7.5 codebase. `v7-development` is retained as the engineering branch for future experimental work before promotion back into `main`.

## Quick navigation

- [What JARVIS can do](#what-jarvis-can-do)
- [Architecture](#architecture)
- [Engineering status](#engineering-status)
- [Quick start](#quick-start)
- [Trusted Local Mode](#trusted-local-mode)
- [Computer Use V2](#computer-use-v2)
- [Controlled self-development](#controlled-self-development)
- [Agent Command Center](#agent-command-center)
- [Testing and CI](#testing-and-ci)
- [Windows build and installer](#windows-build-and-installer)
- [Documentation](#documentation)

---

## Engineering principle

A feature is not treated as complete merely because a file exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Capability truth is reported as:

```text
AVAILABLE | EXPERIMENTAL | DEGRADED | DISABLED | MISSING | BROKEN
```

Action outcomes can be:

```text
VERIFIED | PARTIAL | FAILED | UNVERIFIED
```

JARVIS should not claim that a real-world action succeeded without evidence.

---

## What JARVIS can do

### AI brain and agent runtime

- provider-neutral OpenRouter / OpenAI-compatible / optional local AI adapters
- FAST / SMART / VISION / CODING / PLANNING / REVIEW / SUMMARY / LOCAL routing
- provider circuit breaker with `CLOSED / OPEN / HALF_OPEN` recovery
- persisted mission state
- planner → executor → verifier/reviewer flow
- bounded retry, recovery and replanning
- pause / resume / cancel missions
- capability registry and gap detection
- evidence-based self-evaluation

### Voice and ARC desktop experience

- Hindi / Hinglish / English speech
- interruptible TTS playback
- play / pause / stop controls
- runtime speed controls
- mute/unmute
- active speech termination when JARVIS closes
- Iron-Man-inspired ARC HUD
- THINKING / LISTENING / SPEAKING / PAUSED / ERROR states
- live CPU / RAM / disk / battery / process telemetry
- Agent Command Center

### Vision and Computer Use V2

- image upload and screen vision
- semantic Windows UI Automation targeting
- confidence scoring and ambiguity rejection
- optional local OCR fallback
- UIA-first / OCR-second strategy
- low-confidence no-guess behavior
- post-action evidence and verification
- allowlisted local application control

### Browser V2

- public web research and webpage reading
- HTTP/HTTPS target validation
- local/private target blocking in protected browser-read paths
- prompt-injection pattern detection
- webpage content treated as untrusted data
- browser content cannot override system/security policy

### Memory, RAG and documents

- working memory
- episodic memory
- semantic memory
- procedural memory
- hybrid retrieval
- reinforcement and confidence lifecycle
- contradiction detection
- superseding behavior
- stale/confidence decay
- secret-persistence blocking
- PDF / DOCX / XLSX / XLSM / CSV / TXT / Markdown extraction
- SHA-256 document provenance and duplicate/update detection

### Productivity and development

- notes, todos and reminders
- approved local file/document search and reading
- code project inspection
- controlled code write/test workflows
- Git status / diff / log
- optional Gmail and Calendar integration
- database backup / restore / export / import

### V7.5 engineering intelligence

- Capability Registry
- Self Evaluation Engine
- Capability Gap Detector
- deterministic evaluation benchmarks
- structured observability
- truthful provider-reported cost tracking
- Health System
- Release Readiness Certifier
- sandboxed Self Development
- bounded Self Coding and Self Debugging
- cross-process improvement leases and crash recovery
- repeated safe-workflow learning
- Skill Build / Activation pipeline
- controlled release and history-preserving rollback
- tamper-evident audit integrity chain

---

## Architecture

```text
USER / OPERATOR
      │
      ▼
Context Manager + Capability Registry
      │
      ▼
Provider-Neutral AI + Model Router
      │
      ▼
Mission Orchestrator
UNDERSTAND → PLAN → PERMISSION → EXECUTE → VERIFY
                             │             │
                             │             └→ RECOVER / REPLAN
                             ▼
Capability Security Gate + Audit Integrity
      │
      ▼
Tools / Computer Use / Browser / Documents / Coding
      │
      ▼
Evidence + Memory + Observability + Health
      │
      ▼
Self Evaluation → Gap Detection → Improvement / Skill Proposal
      │
      ▼
Isolated Git Sandbox → Build → Test → Debug → Evaluate → Diff
      │
      ▼
AWAITING APPROVAL
      │
      ▼
Controlled Release → Post-test → History-Preserving Rollback
```

Detailed architecture: [docs/V7-ARCHITECTURE.md](docs/V7-ARCHITECTURE.md)

---

## Engineering status

| System | Status |
|---|---|
| Provider abstraction / model router | ✅ Implemented / CI verified |
| Provider circuit breaker | ✅ Implemented / CI verified |
| Mission state / recovery / verification | ✅ Implemented / CI verified |
| Mission event privacy | ✅ Implemented / CI verified |
| Layered memory / context | ✅ Implemented / CI verified |
| Memory lifecycle V2 | ✅ Implemented / CI verified |
| Capability security / audit | ✅ Implemented / CI verified |
| Audit integrity chain | ✅ Implemented / CI verified |
| Capability Registry | ✅ Implemented / CI verified |
| Self Evaluation / Gap Detection | ✅ Implemented / CI verified |
| Evaluation benchmarks | ✅ Implemented / CI verified |
| Computer Use V2 UIA | ✅ Implemented / CI verified |
| OCR fallback | ✅ Implemented / CI verified |
| Browser V2 security | ✅ Implemented / CI verified |
| Document provenance / dedupe | ✅ Implemented / CI verified |
| Observability / health / cost | ✅ Implemented / CI verified |
| Release Readiness Certifier | ✅ Implemented / CI verified |
| Backup / restore | ✅ Implemented / CI verified |
| Voice media controls | ✅ Implemented / CI verified |
| Agent Command Center | ✅ Integrated |
| Self Development / Coding / Debugging | 🧪 Experimental / tested |
| Offline development | 🧪 Optional / experimental |
| Skill build / activation | 🧪 Experimental / tested |
| Controlled release / rollback | 🧪 Experimental / tested |
| Windows V7 PyInstaller build | ✅ CI package smoke |
| Inno Setup installer | 🖥️ Local workstation validation required |
| V7/V7.5 promotion to `main` | ✅ Completed |

Full status: [docs/V7.5-STATUS.md](docs/V7.5-STATUS.md)

---

## Quick start

### Windows PowerShell

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
git switch main
git pull origin main
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Create local configuration:

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

Never commit `.env`, API keys, OAuth tokens or live runtime databases.

Run diagnostics:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
```

Run the full local test suite:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Launch JARVIS:

```powershell
.\run_desktop.bat
```

Alternative:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

---

## Voice controls

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

Closing the desktop app terminates active playback.

---

## Trusted Local Mode

Default:

```env
TRUSTED_LOCAL_MODE=true
```

Clear allowlisted LOW/MEDIUM local commands can run without repetitive approval prompts, for example:

```text
open chrome
calculator kholo
browser me Python search karo
Downloads me resume dhoondo
Git status dikhao
```

Trusted Local Mode does not mean unrestricted access. Credential scraping, arbitrary destructive shell execution and protected security/self-development boundaries remain blocked. Sensitive writes and side effects remain capability-controlled.

---

## Computer Use V2

Target resolution order:

```text
Windows UI Automation
→ confidence / ambiguity gate
→ optional local OCR fallback
→ action
→ post-action evidence
```

Rules:

- ambiguous UI targets are not guessed
- low-confidence targeting stops safely
- OCR is a fallback, not the primary targeting method
- OCR actions remain PARTIAL until independently verified
- coordinate clicking is not the default strategy

See [docs/V7-COMPUTER-USE.md](docs/V7-COMPUTER-USE.md).

---

## Controlled self-development

The target is controlled improvement, not unrestricted self-rewriting:

```text
Discover
→ Propose
→ Isolated Git Sandbox
→ Build
→ Compile + Tests
→ Bounded Debug / Repair
→ Security + Evaluation
→ Diff Review
→ Approval
→ Controlled Release
→ Post-release Test
→ Rollback if required
```

Safety defaults:

```env
SELF_DEVELOPMENT_ENABLED=true
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
AUTO_ROLLBACK_ENABLED=false
MAX_SELF_REPAIR_ATTEMPTS=3
MAX_FILES_CHANGED=20
MAX_LINES_CHANGED=1200
MAX_BUILD_TIME=300
```

`APPROVED` is not `DEPLOYED`.

Protected areas include secret handling, permission/security policy, sandbox boundaries, rollback controls, `.env`, `.git` and live runtime data.

See [docs/V7-SELF-DEVELOPMENT.md](docs/V7-SELF-DEVELOPMENT.md).

---

## Agent Command Center

Open it from the desktop UI or use:

```text
Ctrl + Shift + C
```

It exposes safe operational views for:

- Mission state and verification
- Health
- Capability Registry
- Observability / provider / model / latency / usage
- Security and audit
- Self Development
- Data / Backup
- Release controls
- Skills lifecycle

Private chain-of-thought is not exposed; only safe state, evidence and operational summaries are shown.

---

## Testing and CI

CI covers:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14
- full unit / integration / security / evaluation discovery
- compile validation
- ResourceWarning failures
- Windows PyInstaller package smoke
- package checks preventing `.env`, live SQLite data and Google OAuth private files from being bundled

A green automated suite proves the software gate only. Physical microphone quality, live provider behavior, real OAuth accounts, desktop interaction and installer install/uninstall still require real workstation evidence.

See [docs/V7-TESTING.md](docs/V7-TESTING.md).

---

## Backup and restore

Database backup uses SQLite-safe backup operations with integrity verification and SHA-256 metadata. Restore/import requires confirmation and creates a pre-restore backup before destructive replacement.

---

## Windows build and installer

Build dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Build application:

```powershell
.\build_windows.ps1
```

Expected output:

```text
dist/JARVIS-OMEGA-V7/JARVIS-OMEGA-V7.exe
```

Build the installer after installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

Expected installer and digest:

```text
dist/installer/JARVIS-AI-OMEGA-Setup-8.0.0-rc1.exe
dist/installer/SHA256.txt
```

AI chat, vision, explicit missions, Edge TTS, and offline TTS use separate configurable
wall-clock limits. A normal chat request has one shared budget across provider retries,
tool continuations, quality repair, and local fallback; each stage does not receive a
fresh full timeout. The default English/Hinglish voice is the Indian female
`en-IN-NeerjaNeural`, with a configured Edge voice fallback and bounded offline backend.

Actual installer installation/uninstallation remains a workstation validation gate.

---

## Documentation

Start at [docs/README.md](docs/README.md).

Key documents:

- [V7 Setup](docs/V7-SETUP.md)
- [V7 Troubleshooting](docs/V7-TROUBLESHOOTING.md)
- [V7 Architecture](docs/V7-ARCHITECTURE.md)
- [V7.5 Engineering Status](docs/V7.5-STATUS.md)
- [V7 Agent / Missions](docs/V7-AGENT.md)
- [V7 Security](docs/V7-SECURITY.md)
- [V7 Memory](docs/V7-MEMORY.md)
- [V7 Computer Use](docs/V7-COMPUTER-USE.md)
- [V7 Browser](docs/V7-BROWSER.md)
- [V7 Tools](docs/V7-TOOLS.md)
- [V7 Testing](docs/V7-TESTING.md)
- [V7 Self Development](docs/V7-SELF-DEVELOPMENT.md)
- [V7 Offline Development](docs/V7-OFFLINE.md)
- [V7 Release Guide](docs/V7-RELEASE.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)

The V6 user guide is retained only as historical/legacy documentation.

---

## Security boundary

JARVIS intentionally does not expose unrestricted destructive shell execution, credential scraping, stealth/persistence bypass or uncontrolled self-modification of security controls.

Self-development cannot silently disable permission policy, audit logging, secret protection, sandbox boundaries, rollback policy or production activation controls.

Read [SECURITY.md](SECURITY.md) before extending local-computer or self-development capabilities.

---

## License

MIT License — see [LICENSE](LICENSE).
