# JARVIS AI OMEGA V7 — Verified Desktop AI Agent

> **V7.5 engineering track: controlled self-evaluation, sandboxed self-development, observability, benchmarks, skills, backup/restore and release safety.**

![Version](https://img.shields.io/badge/JARVIS-V7%20%2F%20V7.5-cyan)
![Python](https://img.shields.io/badge/Python-3.11--3.14-blue)
![Branch](https://img.shields.io/badge/Branch-v7--development-purple)
![CI](https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=v7-development&label=V7.5%20CI)
![Security](https://img.shields.io/badge/Security-Capability%20Gated-red)
![SelfDev](https://img.shields.io/badge/Self--Development-Sandboxed%20%2F%20Experimental-orange)
![License](https://img.shields.io/badge/License-MIT-green)

**Created by Adib Azam.**

```text
OPERATOR: ADIB AZAM
```

JARVIS AI OMEGA is a Windows-first multimodal desktop AI agent. V7 preserves the working ARC desktop experience, voice, vision, documents, web tools, memory and mission execution while rebuilding the internals around verification, recovery, capability security and evidence.

The V7.5 engineering track adds controlled self-evaluation and self-development without turning JARVIS into an unrestricted self-modifying program.

> **Branch strategy:** `main` remains the stable V6 line while `v7-development` contains the active V7/V7.5 engineering work until the final release gate is complete.

---

## Core design rule

A feature is not considered complete because a file exists.

```text
IMPLEMENTED
+ INTEGRATED
+ TESTED
+ VERIFIED
```

The repository intentionally distinguishes **AVAILABLE**, **EXPERIMENTAL**, **DEGRADED**, **DISABLED**, **MISSING** and **BROKEN** capabilities.

---

# Architecture

```text
USER
  │
  ▼
Context Manager
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
Self Evaluation → Gap Detection → Improvement Proposal
  │
  ▼
Isolated Git Sandbox → Build → Test → Debug → Diff
  │
  ▼
AWAITING APPROVAL
  │
  ▼
Controlled Release (separate gate) → Monitor → Rollback if required
```

JARVIS must not claim a real-world action succeeded merely because a tool function returned. Important actions use explicit verification states such as **VERIFIED**, **PARTIAL**, **FAILED** or **UNVERIFIED**.

---

# Current engineering status

| System | Status | Notes |
|---|---|---|
| Provider abstraction | ✅ Implemented | OpenRouter, OpenAI-compatible and local provider foundation |
| Mission state machine | ✅ Implemented | persistence, retry, recovery, replanning, verification, pause/resume/cancel |
| Layered memory/context | ✅ Implemented | working, episodic, semantic, procedural + hybrid retrieval |
| Capability security/audit | ✅ Implemented | granular policies, Approval Center, Trusted Local Mode, secret protection |
| Semantic Computer Use | ✅ Implemented foundation | confidence/no-guess Windows UIA path |
| Browser V2 security | 🔧 V7.5 validation | public-target trust + prompt-injection isolation |
| Capability Registry | ✅ Implemented | runtime-derived capability truth |
| Self Evaluation | ✅ Implemented | evidence-based persisted metrics; unsupported metrics remain N/A |
| Gap Detection | ✅ Implemented | registry, metric and repeated-failure evidence |
| Controlled Self Development | 🧪 Experimental | isolated Git worktree, tests, policy, diff, approval |
| Self Coding / Debugging | 🧪 Experimental | JSON-only sandbox writes + bounded repair loop |
| Offline Development | 🧪 Optional | requires explicitly configured local reasoning model |
| Skill Proposals / Workflow Learning | 🧪 Experimental | proposes reusable skills/workflows; no silent activation |
| Document hash/provenance index | 🔧 V7.5 validation | unchanged/update/duplicate detection |
| Memory lifecycle V2 | 🔧 V7.5 validation | reinforcement, contradiction, superseding, stale/decay layer |
| Provider model router | 🔧 V7.5 validation | FAST/SMART/VISION/CODING/PLANNING/REVIEW/SUMMARY/LOCAL |
| Observability / Cost | 🔧 V7.5 validation | provider/model/latency/usage; cost only when provider explicitly reports it |
| Health system | 🔧 V7.5 validation | PASS/WARNING/FAIL checks without fake remote-health claims |
| Agent Command Center | 🔧 V7.5 validation | mission/health/capability/usage/security/self-dev/data dashboard |
| Backup / Restore | 🔧 V7.5 validation | SQLite backup API + manifest/hash/integrity + pre-restore backup |
| Evaluation Benchmark | 🔧 V7.5 validation | historical deterministic scenario metrics |
| Controlled Release / Rollback | 🧪 Experimental | fast-forward-only deploy + history-preserving Git revert |
| Windows V7 build/installer | 🔧 Scripts updated | final workstation packaging test remains a release step |

Detailed live status: `docs/V7.5-STATUS.md`.

---

# Agent Command Center

The desktop HUD exposes a separate **COMMAND CENTER** so the main chat does not become overcrowded.

Shortcut:

```text
Ctrl + Shift + C
```

Command Center tabs include:

- **MISSION** — goal, current state, steps, evidence, pause/resume/cancel
- **HEALTH** — PASS/WARNING/FAIL subsystem checks
- **CAPABILITIES** — runtime registry and real availability status
- **OBSERVABILITY** — provider/model usage, latency, fallback, reported cost
- **SECURITY** — recent audit/blocked actions
- **SELF DEVELOPMENT** — evaluation, gaps, proposals, sandbox build/review
- **DATA / BACKUP** — database backup/export/restore/import

No private chain-of-thought is shown. The UI only exposes safe state/evidence summaries.

---

# Trusted Local Mode

Normal low/medium-risk local commands should not require repetitive popups.

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

Trusted Local Mode does **not** grant arbitrary shell execution or secret access. High-risk keyboard/mouse actions, file/code writes, email send and calendar writes remain capability-gated. `DENY` and `ALWAYS_ASK` policies override trusted mode.

---

# Controlled Self-Development

The objective is:

```text
Discover improvement
→ build in sandbox
→ test
→ debug with a bounded retry limit
→ evaluate
→ security/policy review
→ show diff/evidence
→ approval
→ controlled release
→ post-release tests
→ rollback if needed
```

It is **not**:

```text
AI silently rewrites production forever
```

### Immutable/protected paths

Normal self-development automation cannot modify:

- `jarvis/security/`
- `jarvis/self_development/policies.py`
- `jarvis/self_development/rollback.py`
- `.env` / secret files
- `.git/`
- runtime `data/`
- protected production workspace data

### Safe defaults

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

`APPROVED` is not the same as `DEPLOYED`.

The release engine requires a clean production worktree, unchanged expected HEAD, fresh tests, approved files, policy pass and fast-forward-only deployment. Rollback uses `git revert`, preserving history.

See `docs/V7-SELF-DEVELOPMENT.md`.

---

# Offline Development

Offline self-development is optional and truthful.

```env
OFFLINE_DEVELOPMENT_ENABLED=true
LOCAL_MODEL_PROVIDER=openai-compatible
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=<your-local-model>
```

Compatible local servers can include Ollama, LM Studio or another OpenAI-compatible runtime.

If no local reasoning model is configured, JARVIS reports:

```text
Offline development is unavailable because no local reasoning model is configured.
```

It does not silently install a model or external dependency.

---

# Self Evaluation and Gap Detection

JARVIS stores historical evaluation evidence for supported metrics such as:

- mission success
- tool success/error rate
- verification success
- recovery/replanning success
- latency
- fallback usage
- safety evidence where available

Metrics that cannot be measured from current evidence are **N/A**, not fabricated.

Capability Gap Detection can produce engineering proposals from:

- missing/degraded capabilities
- low measured metrics
- repeated tool failures
- repeated mission blockers
- repeated safe workflows

A gap is evidence, not permission to edit production.

---

# Skill Generation and Workflow Learning

V7.5 can propose reusable skill manifests with:

```text
skill.json
implementation
tests
documentation
permissions
version
risk
evaluation metadata
```

Generated skill work occurs inside the same Git sandbox/self-development pipeline.

Repeated workflow learning can detect recurring successful tool sequences and propose a reusable skill. Sensitive side-effect sequences such as email sending are intentionally excluded from automatic workflow learning.

No permanent workflow is silently activated.

---

# Browser V2

Public browser-read paths:

- validate HTTP/HTTPS targets
- reject embedded credentials
- reject localhost/private/link-local literal targets
- treat webpage text as untrusted data
- scan common prompt-injection patterns
- never interpret page text as security/system policy

Read/extract evidence can be verified while the returned page text remains untrusted.

See `docs/V7-BROWSER.md`.

---

# Memory and RAG

V7 keeps layered memory and bounded context retrieval. V7.5 adds lifecycle/provenance foundations for:

- reinforcement
- superseding
- contradiction detection
- stale-memory detection
- confidence decay
- document content hashes
- duplicate document detection
- update provenance

Current user instructions always outrank stale memory.

No API keys, passwords, OAuth tokens or session secrets should be persisted as memory.

---

# Documents

Supported extraction includes:

- PDF
- DOCX
- XLSX / XLSM
- CSV
- TXT
- Markdown

V7.5 document indexing adds SHA-256 content provenance. Re-indexing can distinguish:

```text
INDEX
UNCHANGED
UPDATE
DUPLICATE
```

This avoids repeatedly storing identical content.

---

# Provider Router and Cost Tracking

Model route categories:

```text
FAST
SMART
VISION
CODING
PLANNING
REVIEW
SUMMARY
LOCAL
```

Optional environment variables:

```env
FAST_MODEL=
SMART_MODEL=
VISION_MODEL=
CODING_MODEL=
PLANNING_MODEL=
REVIEW_MODEL=
SUMMARY_MODEL=
```

Observability tracks provider/model, latency, success/failure, fallback and usage metadata.

**Cost is never invented.** A numeric cost is displayed only when the provider response explicitly reports it. Otherwise the UI reports cost as N/A.

---

# Voice Player

JARVIS supports spoken output with visible ARC state and runtime controls:

```text
- SPEED
PLAY / PAUSE
STOP
SPEED +
```

Shortcuts:

```text
Esc           stop voice
Ctrl + Space  play/pause
Ctrl + -      slower
Ctrl + +      faster
```

Closing JARVIS terminates active playback instead of leaving the speech process running.

---

# Images and Screen Vision

Desktop:

1. Click **UPLOAD IMAGE** or `Ctrl+O`.
2. Select up to the configured image limit.
3. Ask a question or send with no text for general analysis.
4. `SCREEN VISION` is permission/capability controlled.

Images are validated and resized/compressed before provider upload. Selecting an image does not upload it to GitHub.

Do not send API keys, passwords, recovery codes or banking secrets in screenshots.

---

# Installation — development branch

Windows PowerShell:

```powershell
git fetch origin
git switch v7-development
git pull origin v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Base check:

```powershell
.\.venv\Scripts\python.exe self_check.py
```

V7.5 engineering check:

```powershell
.\.venv\Scripts\python.exe self_check_v75.py
```

Full regression suite:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Launch:

```powershell
.\run_desktop.bat
```

or:

```powershell
.\.venv\Scripts\python.exe desktop_app.py
```

---

# CI / Quality Gate

V7.5 CI targets:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14

CI runs forced bytecode compilation and the full unittest discovery suite. `ResourceWarning` is treated as an error so resource/SQLite handle leaks are not silently ignored.

Never declare release success while CI is red.

See `docs/V7-TESTING.md`.

---

# Backup / Restore

Database backup uses SQLite's backup API rather than copying an actively written file blindly.

Backups include:

- SQLite integrity check
- SHA-256 manifest
- schema version
- size/provenance

Restore/import:

- requires explicit destructive confirmation
- validates the candidate database
- creates a pre-restore backup first
- verifies the restored database again

Private `.env`, OAuth tokens and API keys are not bundled in portable exports.

---

# Windows Build

Build executable:

```powershell
.\build_windows.ps1
```

The script requires PyInstaller to already be deliberately installed. It does not silently install dependencies.

Build installer after installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

Current installer definition:

```text
installer/JARVIS-OMEGA-V7.iss
```

The build does not bundle the operator's `.env`, Google OAuth credentials/tokens, local database or logs.

---

# Documentation

- `docs/V7-AUDIT.md`
- `docs/V7-ARCHITECTURE.md`
- `docs/V7-ARCHITECTURE-ASSESSMENT.md`
- `docs/V7-AGENT.md`
- `docs/V7-SECURITY.md`
- `docs/V7-MEMORY.md`
- `docs/V7-COMPUTER-USE.md`
- `docs/V7-BROWSER.md`
- `docs/V7-TOOLS.md`
- `docs/V7-TESTING.md`
- `docs/V7-SELF-DEVELOPMENT.md`
- `docs/V7-OFFLINE.md`
- `docs/V7.5-STATUS.md`

Legacy V6 documentation may remain when it describes historical V6 behavior; current behavior must be identified as V7/V7.5 rather than blindly renaming history.

---

# Security boundary

This project intentionally does not expose unrestricted destructive shell execution, credential scraping, stealth/persistence bypass or self-modification of security controls.

Self-development may improve normal application capabilities, but it must not silently modify permission policy, audit logging, secret protection, sandbox boundaries, rollback policy or production activation controls.

---

# License

MIT License.
