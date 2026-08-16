# JARVIS AI OMEGA V7 / V7.5 — Testing & Evaluation

## Quality rule

A feature is not called complete merely because a module exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

CI green is required for release readiness, but physical-device and external-account behavior may still need workstation validation.

## Local developer gate

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the full suite after touching shared runtime, security, memory, computer-use, self-development or storage code.

## CI matrix

The V7.5 workflow targets:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14

Regression jobs run forced compilation plus full unittest discovery.

`ResourceWarning` is promoted to an error so leaked files/SQLite handles cannot be ignored.

## Windows packaging gate

After Windows regression passes, CI performs a PyInstaller smoke build.

The gate verifies that:

- `JARVIS-OMEGA-V7.exe` is produced;
- the distribution does not intentionally bundle `.env`;
- live `.db`, `.sqlite` or `.sqlite3` runtime data is excluded;
- Google OAuth credential/token files are excluded.

Build dependencies come from `requirements-build.txt`.

## Test categories

The repository includes coverage for:

### Foundation / providers

- provider-neutral contracts
- typed/configuration errors
- model/provider error classification
- route/model behavior

### Missions / agent reliability

- persisted missions
- verified successful reasoning paths
- retry eligibility
- recovery / replanning
- failure-history preservation
- pause / resume / cancel
- PARTIAL vs VERIFIED evidence behavior

### Security

- capability profiles
- Trusted Local Mode boundaries
- ALWAYS_ASK / explicit DENY precedence
- unknown-tool denial
- secret detection/redaction
- audit safety
- high-risk permission bypass attempts

### Memory / RAG / documents

- layered memory/context
- schema migration
- hybrid retrieval
- reinforcement
- superseding / current truth
- secret persistence blocking
- document content-hash duplicate/update behavior
- memory lifecycle contradiction/stale/decay behavior

### Computer Use / browser

- semantic target confidence
- ambiguity rejection
- no-guess behavior
- post-action evidence
- OCR fallback integration
- browser URL trust policy
- private/local target rejection
- prompt-injection isolation
- untrusted webpage content handling

### V7.5 self-evaluation / self-development

- persisted evaluation history
- measured rates from evidence
- unsupported metric `N/A` behavior
- capability gap detection
- proposal persistence
- sandbox path isolation
- immutable-core protection
- bounded self-coding / repair
- offline-development truthfulness
- before/after benchmark binding

### Skills / workflow learning

- repeated safe workflow proposal
- sensitive side-effect sequence rejection
- skill manifest completeness
- sandbox build preparation
- deployed-only activation
- explicit operator activation requirement

### Data / release

- backup integrity manifest/hash
- export/import round trip
- destructive restore confirmation
- pre-restore backup
- controlled release gating
- production self-modification default OFF
- history-preserving rollback

### Observability / health

- safe event persistence
- secret redaction
- provider fallback/failure recording
- token aggregation
- cost only when provider explicitly reports it
- real local database health checks

## Evaluation benchmark

`jarvis/evaluation/benchmark.py` stores deterministic scenario results historically.

Supported metric categories include:

- task success
- tool accuracy
- verification accuracy
- recovery
- replanning
- safety
- memory accuracy
- computer-use accuracy
- browser accuracy
- average latency

Before/after comparison treats lower latency as better and success/accuracy metrics as higher-is-better.

A model statement such as “performance improved” is not benchmark evidence.

## Adversarial security expectations

Tests should fail safely for attempts involving:

- prompt injection
- secret persistence/extraction
- private browser targets
- unknown tools
- permission bypass
- sandbox escape
- security-core self-modification
- unrestricted shell exposure
- Trusted Local Mode high-risk bypass

Security failures block release readiness.

## Workstation smoke testing

CI cannot prove every real-device behavior.

Before stable release, test on the actual Windows workstation:

- desktop app launches normally
- Agent Command Center opens
- configured provider answers
- voice starts/stops/changes speed correctly
- closing the app stops playback
- microphone/wake word if enabled
- Screen Vision permission/capture if enabled
- Chrome/allowlisted app control
- UIA semantic targeting
- OCR fallback if locally configured
- backup/integrity
- optional Gmail/Calendar only if included in release claim
- packaged EXE launch
- Inno installer install/uninstall after local compilation

See [V7-RELEASE.md](V7-RELEASE.md).

## How to debug red CI

1. identify the first meaningful failure;
2. reproduce it on the closest local Python/platform when possible;
3. isolate the root contract being violated;
4. fix the implementation;
5. rerun focused tests;
6. rerun the full suite;
7. confirm other platforms still pass.

Do not add sleeps, skip tests or hard-code expected values unless that change represents the actual contract.

## Release rule

Do not declare a release ready while required CI is red.

Do not claim optional hardware/provider/account features were validated unless they were actually tested in that environment.
