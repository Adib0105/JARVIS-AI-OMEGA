# JARVIS AI OMEGA — Documentation Hub

This directory contains current engineering documentation plus historical V6/V7/V7.5 filenames retained for link compatibility. Product versioning comes only from `jarvis.version.APP_VERSION`.

The active engineering/release-candidate branch is `v7-development`. Do not infer the current application version or the state of `main` from historical branch/document names.

## Start here

| Goal | Document |
|---|---|
| Install and run the current release candidate | [V7-SETUP.md](V7-SETUP.md) |
| Understand current release evidence/status | [V7.5-STATUS.md](V7.5-STATUS.md) |
| Run tests and quality gates | [V7-TESTING.md](V7-TESTING.md) |
| Reproduce dependencies | [DEPENDENCIES.md](DEPENDENCIES.md) |
| Validate real Windows/device behavior | [WINDOWS-E2E-CHECKLIST.md](WINDOWS-E2E-CHECKLIST.md) |
| Fix common Windows/runtime issues | [V7-TROUBLESHOOTING.md](V7-TROUBLESHOOTING.md) |
| Understand security boundaries | [V7-SECURITY.md](V7-SECURITY.md) |
| Prepare a release | [V7-RELEASE.md](V7-RELEASE.md) |

## Architecture and subsystem docs

- [V7-ARCHITECTURE.md](V7-ARCHITECTURE.md) — runtime architecture and reliability model
- [V7-AGENT.md](V7-AGENT.md) — mission state machine, planning, verification and recovery
- [V7-MEMORY.md](V7-MEMORY.md) — layered memory, RAG and lifecycle behavior
- [V7-COMPUTER-USE.md](V7-COMPUTER-USE.md) — UIA-first computer control and OCR fallback
- [V7-BROWSER.md](V7-BROWSER.md) — browser trust model and prompt-injection isolation
- [V7-TOOLS.md](V7-TOOLS.md) — tool families, capabilities and verification
- [V7-SELF-DEVELOPMENT.md](V7-SELF-DEVELOPMENT.md) — sandboxed self-improvement pipeline
- [V7-OFFLINE.md](V7-OFFLINE.md) — optional local OpenAI-compatible development model

## Audit snapshots

The following documents are engineering snapshots tied to their stated audit context/commit. They can contain findings that have since been fixed and should not be treated as the current release certificate:

- [V7-AUDIT.md](V7-AUDIT.md)
- [V7-ARCHITECTURE-ASSESSMENT.md](V7-ARCHITECTURE-ASSESSMENT.md)
- [V7.5-HARDENING-AUDIT.md](V7.5-HARDENING-AUDIT.md)
- [V8-ENGINEERING-AUDIT.md](V8-ENGINEERING-AUDIT.md)

For current state, prefer the README, status, release, testing and exact-commit CI evidence.

## Evidence language

Product documentation uses `VERIFIED`, `TESTED`, `EXPERIMENTAL`, `LIMITED`, `NOT VERIFIED` and `PLANNED` for release claims.

Runtime diagnostics use:

```text
INSTALLED | CONFIGURED | LOCAL_FUNCTIONAL | INTEGRATION_TESTED
DEVICE_VERIFIED | E2E_VERIFIED | DEGRADED | FAILED | NOT_TESTED
```

Capability-registry operational states are separate from those evidence levels. A feature is not complete merely because a module imports or a dependency exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

## Safety model

JARVIS is capability-gated, not an unrestricted shell. The controlled self-development path is:

```text
Discover → Propose → Sandbox → Build → Test → Security/Evaluation
→ Diff → Approval → Controlled Release → Post-test → Rollback if required
```

Production self-modification remains disabled by default. Unknown/unprofiled tools fail closed and real-device/live-service claims remain unverified without qualifying evidence.

## Historical documentation

[V6-USER-GUIDE.md](V6-USER-GUIDE.md) is retained only as historical documentation. Historical filenames do not define current product behavior or version.
