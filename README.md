# JARVIS AI OMEGA V7 / V7.5

<p align="center">
  <strong>Reliable • Multimodal • Capability-Gated • Evidence-Driven Desktop AI Agent</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/JARVIS-V7%20%2F%20V7.5-00d9ff">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11--3.14-3776ab">
  <img alt="Branch" src="https://img.shields.io/badge/Branch-v7--development-8a2be2">
  <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=v7-development&label=CI">
  <img alt="Security" src="https://img.shields.io/badge/Security-Capability%20Gated-dc3545">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-2ea44f">
</p>

<p align="center">
  <strong>Created by Adib Azam</strong><br>
  <code>OPERATOR: ADIB AZAM</code>
</p>

---

JARVIS AI OMEGA is a **Windows-first multimodal desktop AI agent** built around a simple rule: an AI assistant should not merely call tools — it should understand intent, respect permissions, execute carefully, verify outcomes, preserve evidence and recover when something fails.

V7 keeps the Iron-Man-inspired ARC desktop experience, voice, vision, documents, memory, web tools and productivity workflows while rebuilding the internals around reliability, capability security, evidence-based verification and controlled self-improvement.

> **Branch strategy:** `main` remains the stable V6 line. `v7-development` contains the current V7/V7.5 engineering track until workstation smoke testing and the final release decision.

## Quick navigation

- [What JARVIS can do](#what-jarvis-can-do)
- [Architecture](#architecture)
- [Current engineering status](#current-engineering-status)
- [Quick start](#quick-start)
- [Voice controls](#voice-controls)
- [Computer Use V2](#computer-use-v2)
- [Trusted Local Mode](#trusted-local-mode)
- [Self-evaluation and controlled self-development](#self-evaluation-and-controlled-self-development)
- [Agent Command Center](#agent-command-center)
- [Testing and CI](#testing-and-ci)
- [Windows build and installer](#windows-build-and-installer)
- [Documentation hub](#documentation-hub)
- [Roadmap](ROADMAP.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

---

## Engineering principle

A feature is not considered complete merely because a file exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Runtime capability status is expressed as:

```text
AVAILABLE | EXPERIMENTAL | DEGRADED | DISABLED | MISSING | BROKEN
```

JARVIS must not claim a real-world action succeeded just because a tool function returned successfully. Important actions can report **VERIFIED**, **PARTIAL**, **FAILED** or **UNVERIFIED** depending on observable evidence.

---

## What JARVIS can do

### AI and agent runtime

- provider-neutral OpenRouter / OpenAI-compatible / optional local AI abstraction
- FAST / SMART / VISION / CODING / PLANNING / REVIEW / SUMMARY / LOCAL routing categories
- persisted mission planning and execution
- verification, retry, recovery and replanning
- pause / resume / cancel mission controls
- evidence-based result reporting

### Voice and desktop experience

- Hindi / Hinglish / English speech
- interruptible voice playback
- play / pause / stop controls
- runtime speech speed control
- speech termination when the application closes
- Iron-Man-inspired ARC desktop HUD
- Agent Command Center

### Computer and browser use

- semantic Windows UI Automation targeting
- confidence and ambiguity gates
- optional local OCR fallback
- no-guess policy for low-confidence targets
- browser public-target checks
- prompt-injection isolation
- untrusted webpage-content handling

### Memory, RAG and documents

- working memory
- episodic memory
- semantic memory
- procedural memory
- hybrid retrieval
- reinforcement and confidence lifecycle
- contradiction and superseding behavior
- stale/confidence decay
- PDF, DOCX, XLSX/XLSM, CSV, TXT and Markdown extraction
- content-hash document provenance and duplicate detection

### Productivity and development

- notes, todos and reminders
- approved local file/document search and reading
- code project inspection
- controlled code write/test workflow
- Git status/diff/log tools
- optional Gmail and Calendar integration
- backup / restore / export / import

### V7.5 engineering intelligence

- Capability Registry
- Self Evaluation
- Capability Gap Detection
- deterministic evaluation benchmarks
- structured observability
- Health System
- truthful provider-reported cost tracking
- sandboxed Self Development
- bounded Self Coding / Self Debugging
- repeated safe-workflow learning
- Skill Build / Activation pipeline
- controlled release and rollback gates

---

## Architecture

```text
USER
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
                         │            │
                         │            └→ RECOVER / REPLAN
                         ▼
Capability Security Gate + Audit
  │
  ▼
Tools / Computer Use / Browser / Documents / Coding
  │
  ▼
Evidence + Memory + Observability
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

## Current engineering status

| System | Status |
|---|---|
| Provider abstraction / model router | ✅ Implemented / verified in CI |
| Mission state machine / recovery | ✅ Implemented / verified in CI |
| Layered memory / context | ✅ Implemented / verified in CI |
| Memory lifecycle V2 | ✅ Implemented / verified in CI |
| Capability security / audit | ✅ Implemented / verified in CI |
| Capability Registry | ✅ Implemented / verified in CI |
| Self Evaluation / Gap Detection | ✅ Implemented / verified in CI |
| Evaluation benchmarks | ✅ Implemented / verified in CI |
| Computer Use V2 UIA | ✅ Implemented / verified in CI |
| OCR fallback integration | ✅ Implemented / verified in CI |
| Browser V2 security | ✅ Implemented / verified in CI |
| Document provenance / dedupe | ✅ Implemented / verified in CI |
| Observability / health / cost | ✅ Implemented / verified in CI |
| Backup / restore | ✅ Implemented / verified in CI |
| Voice media controls | ✅ Implemented / verified in CI |
| Agent Command Center | ✅ Integrated |
| Self Development / Coding / Debugging | 🧪 Experimental / tested |
| Offline development | 🧪 Optional / experimental |
| Skill build / activation | 🧪 Experimental / tested |
| Controlled release / rollback | 🧪 Experimental / tested |
| Windows V7 PyInstaller build | ✅ CI-gated package smoke |
| Inno Setup installer | 🖥️ Local workstation compilation required |
| V7 merge to `main` | ⏳ Not yet performed |

Full truth matrix: [docs/V7.5-STATUS.md](docs/V7.5-STATUS.md)

---

## Quick start

### Windows PowerShell

```powershell
git clone https://github.com/Adib0105/JARVIS-AI-OMEGA.git
cd JARVIS-AI-OMEGA
git fetch origin
git switch v7-development
git pull origin v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Copy the environment template:

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

Never commit `.env` or expose API keys in screenshots/logs.

### Run diagnostics

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
```

### Launch desktop JARVIS

```powershell
.\run_desktop.bat
```

Alternative:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

Complete setup guide: [docs/V7-SETUP.md](docs/V7-SETUP.md)

---

## Voice controls

The always-visible voice strip provides:

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

Closing JARVIS terminates active playback instead of leaving speech running in the background.

---

## Trusted Local Mode

Ordinary allowlisted LOW/MEDIUM local commands can run without repetitive approval popups.

Examples:

```text
open chrome
calculator kholo
browser me Python search karo
Downloads me resume dhoondo
Git status dikhao
```

Default:

```env
TRUSTED_LOCAL_MODE=true
```

Trusted Local Mode does **not** grant arbitrary shell execution, credential scraping or destructive unrestricted access. High-risk keyboard/mouse control, file/code writes, email send and calendar writes remain capability-gated.

---

## Computer Use V2

Target resolution order:

```text
Windows UI Automation
→ confidence / ambiguity gate
→ optional local OCR fallback when appropriate
→ action
→ post-action evidence
```

Key rules:

- ambiguous UIA results are never bypassed with OCR guesses
- low-confidence targets stop safely
- OCR is optional and requires local dependencies
- OCR-resolved actions remain PARTIAL until independently verified
- raw coordinate clicking is not the primary strategy

See [docs/V7-COMPUTER-USE.md](docs/V7-COMPUTER-USE.md).

---

## Browser V2 security

Public browser-read paths:

- accept valid HTTP/HTTPS targets
- reject embedded credentials
- block obvious local/private literal targets
- treat webpage content as untrusted data
- detect common prompt-injection patterns
- never allow webpage text to replace system/security policy

See [docs/V7-BROWSER.md](docs/V7-BROWSER.md).

---

## Self-evaluation and controlled self-development

V7.5 can measure its own observed mission/tool performance, identify evidence-backed capability gaps and prepare improvements in an isolated Git sandbox.

```text
Discover improvement
→ create evidence-backed proposal
→ isolated self-improvement/IMP-* worktree
→ bounded code generation
→ compile + full regression
→ bounded repair
→ security/policy review
→ evaluation + diff
→ AWAITING_APPROVAL
→ APPROVED
→ controlled release
→ post-release test
→ rollback if required
```

It is intentionally **not** an unrestricted self-rewriting system.

Safe defaults:

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

Protected areas include security policy, secret handling, self-development policy, rollback controls, `.env`, `.git` and runtime data.

See [docs/V7-SELF-DEVELOPMENT.md](docs/V7-SELF-DEVELOPMENT.md).

---

## Skills and workflow learning

V7.5 can detect repeated safe workflows and propose reusable skill manifests. Generated skill code uses the same sandbox/test/security/diff gates as self-development.

A skill cannot become ACTIVE until its linked improvement is deployed, required files exist, evaluation passes and operator activation is explicit.

Sensitive side-effect sequences are not silently converted into permanent automation.

---

## Agent Command Center

Open from the desktop UI or press:

```text
Ctrl + Shift + C
```

Views include:

- **MISSION** — live mission state, steps and verification
- **HEALTH** — PASS/WARNING/FAIL subsystem checks
- **CAPABILITIES** — runtime capability truth
- **OBSERVABILITY** — provider/model/latency/fallback/usage information
- **SECURITY** — audit and blocked/sensitive behavior
- **SELF DEVELOPMENT** — evaluations, gaps and improvement proposals
- **DATA / BACKUP** — integrity, backup, export and restore
- **RELEASE** — guarded deploy/rollback workflow
- **SKILLS** — proposal, build, activation and disable lifecycle

No private chain-of-thought is exposed; the UI shows safe state/evidence summaries.

---

## Memory, RAG and documents

V7/V7.5 includes:

- working / episodic / semantic / procedural memory
- hybrid local retrieval
- current request priority over stale memory
- reinforcement and explicit verification
- contradiction detection and superseding
- stale/confidence decay
- secret-persistence blocking
- SHA-256 document provenance and duplicate/update detection

Supported document families include PDF, DOCX, XLSX/XLSM, CSV, TXT and Markdown.

See [docs/V7-MEMORY.md](docs/V7-MEMORY.md).

---

## Observability and cost

Observability records safe metadata such as provider/model, latency, success/failure, fallback and token counters.

**Cost is never invented.** A numeric cost appears only when the provider explicitly reports it; otherwise it remains `N/A`.

---

## Testing and CI

Local quality gate:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

CI covers:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14
- full unit / integration / security / evaluation discovery
- `ResourceWarning` as an error
- Windows PyInstaller package smoke
- package rejection when `.env`, live SQLite data or Google OAuth private files are bundled

Never declare release readiness while CI is red.

See [docs/V7-TESTING.md](docs/V7-TESTING.md).

---

## Backup and restore

Backups use SQLite's backup API and include integrity verification, SHA-256 manifest metadata and schema information.

Restore/import is destructive, requires confirmation, creates a pre-restore backup and verifies database integrity again.

Portable exports and builds must not intentionally bundle `.env`, API keys, Google OAuth credentials/tokens or the live JARVIS database.

---

## Windows build and installer

Install build dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Build V7 application:

```powershell
.\build_windows.ps1
```

Expected executable:

```text
dist/JARVIS-OMEGA-V7/JARVIS-OMEGA-V7.exe
```

Build installer after installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

Release checklist: [docs/V7-RELEASE.md](docs/V7-RELEASE.md)

---

## Documentation hub

Start at [docs/README.md](docs/README.md).

Key documents:

- [Setup](docs/V7-SETUP.md)
- [Troubleshooting](docs/V7-TROUBLESHOOTING.md)
- [Architecture](docs/V7-ARCHITECTURE.md)
- [Engineering status](docs/V7.5-STATUS.md)
- [Agent / missions](docs/V7-AGENT.md)
- [Security](docs/V7-SECURITY.md)
- [Memory](docs/V7-MEMORY.md)
- [Computer Use](docs/V7-COMPUTER-USE.md)
- [Browser](docs/V7-BROWSER.md)
- [Tools](docs/V7-TOOLS.md)
- [Testing](docs/V7-TESTING.md)
- [Self Development](docs/V7-SELF-DEVELOPMENT.md)
- [Offline development](docs/V7-OFFLINE.md)
- [Release guide](docs/V7-RELEASE.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)

Legacy [docs/V6-USER-GUIDE.md](docs/V6-USER-GUIDE.md) is retained for the stable V6 line and historical behavior.

---

## Security boundary

JARVIS intentionally does not expose unrestricted destructive shell execution, credential scraping, stealth/persistence bypass or uncontrolled self-modification of security controls.

Self-development may improve ordinary application capabilities, but it cannot silently disable permission policy, audit logging, secret protection, sandbox boundaries, rollback policy or production activation controls.

Read [SECURITY.md](SECURITY.md) before adding local-computer or self-development capabilities.

---

## Contributing

Contributions should be focused, tested, auditable and permission-aware. See [CONTRIBUTING.md](CONTRIBUTING.md) and use the repository's issue/PR templates.

---

## License

MIT License — see [LICENSE](LICENSE).
