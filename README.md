# JARVIS AI OMEGA V7 — Verified Desktop AI Agent

> **V7.5 engineering track:** self-evaluation, gap detection, sandboxed self-development, Computer Use V2, observability, benchmarks, skills, backup/restore and controlled release safety.

![Version](https://img.shields.io/badge/JARVIS-V7%20%2F%20V7.5-cyan)
![Python](https://img.shields.io/badge/Python-3.11--3.14-blue)
![Branch](https://img.shields.io/badge/Branch-v7--development-purple)
![CI](https://img.shields.io/github/actions/workflow/status/Adib0105/JARVIS-AI-OMEGA/ci.yml?branch=v7-development&label=V7.5%20CI)
![Security](https://img.shields.io/badge/Security-Capability%20Gated-red)
![SelfDev](https://img.shields.io/badge/Self--Development-Sandboxed%20%2F%20Operator--Gated-orange)
![License](https://img.shields.io/badge/License-MIT-green)

**Created by Adib Azam.**

```text
OPERATOR: ADIB AZAM
```

JARVIS AI OMEGA is a Windows-first multimodal desktop AI agent. V7 keeps the ARC desktop experience, voice, vision, documents, web tools, memory and mission execution while rebuilding the internals around verification, recovery, capability security and evidence.

The V7.5 engineering track adds controlled self-evaluation and self-development without turning JARVIS into an unrestricted self-modifying program.

> **Branch strategy:** `main` remains the stable V6 line. `v7-development` contains active V7/V7.5 engineering work until operator workstation smoke testing and the final release decision.

---

## Engineering rule

A feature is not considered complete merely because a file exists.

```text
IMPLEMENTED
+ INTEGRATED
+ TESTED
+ VERIFIED
```

Runtime capability status uses:

```text
AVAILABLE | EXPERIMENTAL | DEGRADED | DISABLED | MISSING | BROKEN
```

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
Controlled Release → Post-test → History-preserving Rollback if required
```

JARVIS must not claim a real-world action succeeded merely because a tool function returned. Important actions expose states such as **VERIFIED**, **PARTIAL**, **FAILED** and **UNVERIFIED**.

---

## Current V7.5 engineering status

| System | Status | Notes |
|---|---|---|
| Provider abstraction + router | ✅ Implemented/tested | OpenRouter, OpenAI-compatible and optional local route |
| Mission state machine | ✅ Implemented/tested | persistence, verification, retry, recovery, replanning, pause/resume/cancel |
| Layered memory/context | ✅ Implemented/tested | working, episodic, semantic, procedural + hybrid retrieval |
| Memory lifecycle V2 | ✅ Implemented/tested | reinforcement, contradiction, superseding, stale/confidence decay |
| Capability security/audit | ✅ Implemented/tested | Approval Center, Trusted Local Mode, secret protection |
| Capability Registry | ✅ Implemented/tested | runtime-derived capability truth |
| Self Evaluation + Gap Detection | ✅ Implemented/tested | evidence-based historical metrics; unsupported metrics remain N/A |
| Evaluation Benchmark | ✅ Implemented/tested | deterministic before/after scenario metrics |
| Computer Use V2 | ✅ Integrated/tested | UIA-first + stricter optional local OCR fallback + no-guess policy |
| Browser V2 security | ✅ Implemented/tested | public-target checks + prompt-injection isolation |
| Document provenance/dedupe | ✅ Implemented/tested | SHA-256 unchanged/update/duplicate decisions |
| Observability / Cost | ✅ Implemented/tested | provider/model/latency/fallback/token usage; cost only when explicitly reported |
| Health System | ✅ Implemented/tested | PASS/WARNING/FAIL without fake remote-health claims |
| Agent Command Center | ✅ Integrated | Mission, Health, Capabilities, Observability, Security, Self-Dev, Data, Release, Skills |
| Backup / Restore | ✅ Implemented/tested | SQLite backup API, integrity, SHA-256 manifest, pre-restore backup |
| Self Development / Coding / Debugging | 🧪 Experimental | isolated sandbox only; bounded changes and repair |
| Offline Development | 🧪 Optional | requires explicitly configured local reasoning model |
| Workflow Learning | ✅ Implemented/tested | proposes repeated safe workflows; no silent automation activation |
| Skill Generation | 🧪 Experimental | sandbox build/test plus deployed-only activation gate |
| Controlled Release / Rollback | 🧪 Experimental | explicit enablement/approval; fast-forward deploy; Git revert rollback |
| Windows V7 build | 🔬 CI-gated | PyInstaller package smoke + private runtime file exclusion |
| Inno Setup installer | 🖥️ Workstation step | requires Inno Setup 6 locally |

Detailed matrix: `docs/V7.5-STATUS.md`.

---

## Agent Command Center

Open from the desktop UI or use:

```text
Ctrl + Shift + C
```

Tabs include:

- **MISSION** — mission status, steps, verification, pause/resume/cancel
- **HEALTH** — PASS/WARNING/FAIL subsystem checks
- **CAPABILITIES** — live runtime capability registry
- **OBSERVABILITY** — model/provider usage, latency, fallback and reported cost
- **SECURITY** — audit and blocked/sensitive actions
- **SELF DEVELOPMENT** — evaluation, gaps, proposals, sandbox build/review
- **DATA / BACKUP** — backup/export/restore/import
- **RELEASE** — guarded deploy/rollback controls
- **SKILLS** — gap → skill proposal → sandbox build → deployed-only activation

No private chain-of-thought is exposed; only safe state/evidence summaries are shown.

---

## Trusted Local Mode

Normal low/medium-risk allowlisted local commands can run without repetitive popups.

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

This does **not** grant arbitrary shell execution or credential access. Higher-risk writes, keyboard/mouse control, email send and calendar writes remain capability-gated.

---

## Computer Use V2

Target resolution order:

```text
Windows UI Automation
→ confidence / ambiguity check
→ optional local OCR fallback only if UIA has no confident target
→ action
→ post-action evidence
```

Rules:

- ambiguous UIA results are never bypassed with OCR guesses
- low-confidence targets stop safely
- OCR requires local OCR dependencies and is optional
- OCR-resolved actions remain **PARTIAL** until the higher-level outcome is independently verified
- raw coordinate clicking remains a guarded low-level fallback, not the primary target strategy

---

## Browser V2

Public browser-read paths:

- require valid HTTP/HTTPS URLs
- reject embedded credentials
- reject localhost/private/link-local/reserved literal targets
- treat webpage text as untrusted data
- scan common prompt-injection patterns
- never turn webpage instructions into system/security policy

---

## Controlled self-development

Target lifecycle:

```text
Discover improvement
→ create evidence-backed proposal
→ isolated self-improvement/IMP-* Git worktree
→ bounded code generation
→ compile + full tests
→ bounded self-debug repair
→ security/policy review
→ evaluation + diff
→ AWAITING_APPROVAL
→ APPROVED
→ controlled release
→ post-release tests
→ rollback if needed
```

It is intentionally **not**:

```text
AI silently rewrites production forever
```

Protected areas include security policy, secret handling, self-development policy, rollback controls, `.env`, `.git` and runtime data.

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

The release engine requires fresh tests, immutable-core policy pass, exact reviewed files, clean production worktree, unchanged expected HEAD and fast-forward-only deployment. Rollback uses history-preserving `git revert`.

See `docs/V7-SELF-DEVELOPMENT.md`.

---

## Skill generation and workflow learning

V7.5 can propose reusable skill manifests containing:

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

Generated skill code uses the same isolated self-development sandbox. A skill cannot become ACTIVE until:

1. its linked improvement proposal is `DEPLOYED`,
2. required production files exist,
3. evaluation metadata is PASS/PASSED/VERIFIED/READY,
4. operator activation is explicit.

Repeated successful safe workflows can be proposed as reusable workflows. Sensitive side-effect sequences are not silently learned into permanent automation.

---

## Offline development

Optional local reasoning:

```env
OFFLINE_DEVELOPMENT_ENABLED=true
LOCAL_MODEL_PROVIDER=openai-compatible
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=<your-local-model>
```

Compatible local servers can include Ollama, LM Studio or another OpenAI-compatible runtime. No local model is silently installed.

---

## Memory / RAG / documents

V7/V7.5 memory includes:

- working, episodic, semantic and procedural layers
- hybrid local retrieval
- current user input higher priority than stale memory
- reinforcement and explicit verification
- superseding and contradiction detection
- stale/confidence decay
- secret-persistence blocking

Document extraction supports PDF, DOCX, XLSX/XLSM, CSV, TXT and Markdown. V7.5 indexing adds SHA-256 provenance so unchanged content can avoid re-indexing.

---

## Provider routing and observability

Route categories:

```text
FAST | SMART | VISION | CODING | PLANNING | REVIEW | SUMMARY | LOCAL
```

Optional model overrides:

```env
FAST_MODEL=
SMART_MODEL=
VISION_MODEL=
CODING_MODEL=
PLANNING_MODEL=
REVIEW_MODEL=
SUMMARY_MODEL=
```

Observability records provider/model, latency, success/failure, fallback and safe usage counters.

**Cost is never invented.** A numeric cost appears only when the provider response explicitly reports it; otherwise cost is N/A.

---

## Voice Player

Runtime controls:

```text
- SPEED | PLAY / PAUSE | STOP | SPEED +
```

Shortcuts:

```text
Esc           stop voice
Ctrl + Space  play/pause
Ctrl + -      slower
Ctrl + +      faster
```

Closing JARVIS terminates active playback instead of leaving speech running in the background.

---

## Install and test `v7-development`

Windows PowerShell:

```powershell
git fetch origin
git switch v7-development
git pull origin v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Engineering checks:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
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

## CI quality gate

CI covers:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14
- forced `compileall`
- full unittest/integration/security/evaluation discovery
- `ResourceWarning` as error
- Windows PyInstaller package smoke after Windows regression
- package rejection if `.env`, live DB/SQLite or Google OAuth private files are bundled

Never declare release success while CI is red.

---

## Backup / restore

Backups use SQLite's backup API and include:

- integrity verification
- SHA-256 manifest
- schema version
- provenance/size

Restore/import requires explicit destructive confirmation, creates a pre-restore backup and verifies the restored database again.

Portable exports and Windows builds do not intentionally bundle `.env`, API keys, Google OAuth credentials/tokens or the live JARVIS database.

---

## Windows build / installer

Build EXE:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_windows.ps1
```

Installer after installing Inno Setup 6:

```powershell
.\build_installer.ps1
```

Installer definition:

```text
installer/JARVIS-OMEGA-V7.iss
```

---

## Documentation

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

Legacy V6 documentation may remain when it describes historical behavior; current functionality is identified explicitly as V7/V7.5.

---

## Security boundary

This project intentionally does not expose unrestricted destructive shell execution, credential scraping, stealth/persistence bypass or uncontrolled self-modification of security controls.

Self-development can improve ordinary application capabilities, but it cannot silently disable permission policy, audit logging, secret protection, sandbox boundaries, rollback policy or production activation controls.

---

## License

MIT License.
