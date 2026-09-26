# JARVIS AI OMEGA — Documentation Hub

This directory is the source of truth for the V7.7 engineering track and its V7/V7.5/V7.6 foundations.

> `main` contains the promoted V7 line. New release claims still require the documented automated and real-Windows evidence gates.

## Start here

| Goal | Document |
|---|---|
| Understand V7.7 five-layer routing and privacy | [V7.7-FIVE-LAYER-INTELLIGENCE.md](V7.7-FIVE-LAYER-INTELLIGENCE.md) |
| Review the V7.6 background-wake launch pack | [V7.6-LAUNCH-PACK.md](V7.6-LAUNCH-PACK.md) |
| Configure always-on wake and tray behavior | [BACKGROUND-WAKE.md](BACKGROUND-WAKE.md) |
| Install and run the current V7 line | [V7-SETUP.md](V7-SETUP.md) |
| Understand the architecture | [V7-ARCHITECTURE.md](V7-ARCHITECTURE.md) |
| See current implementation status | [V7.5-STATUS.md](V7.5-STATUS.md) |
| Run tests and quality gates | [V7-TESTING.md](V7-TESTING.md) |
| Fix common Windows/runtime issues | [V7-TROUBLESHOOTING.md](V7-TROUBLESHOOTING.md) |
| Understand security boundaries | [V7-SECURITY.md](V7-SECURITY.md) |
| Prepare a release | [V7-RELEASE.md](V7-RELEASE.md) |

## Core engineering docs

- [V7-AUDIT.md](V7-AUDIT.md) — repository audit and technical debt baseline
- [V7-ARCHITECTURE.md](V7-ARCHITECTURE.md) — runtime architecture and reliability model
- [V7.7-FIVE-LAYER-INTELLIGENCE.md](V7.7-FIVE-LAYER-INTELLIGENCE.md) — ordered AI/ML/deep-learning/GenAI/LLM routing, privacy and controls
- [V7-ARCHITECTURE-ASSESSMENT.md](V7-ARCHITECTURE-ASSESSMENT.md) — deeper design assessment
- [V7-AGENT.md](V7-AGENT.md) — mission state machine, planning, verification and recovery
- [V7-MEMORY.md](V7-MEMORY.md) — layered memory, RAG and lifecycle behavior
- [V7-COMPUTER-USE.md](V7-COMPUTER-USE.md) — UIA-first computer control and OCR fallback
- [V7-BROWSER.md](V7-BROWSER.md) — browser trust model and prompt-injection isolation
- [V7-TOOLS.md](V7-TOOLS.md) — tool families, capabilities and verification
- [V7-SELF-DEVELOPMENT.md](V7-SELF-DEVELOPMENT.md) — sandboxed self-improvement pipeline
- [V7-OFFLINE.md](V7-OFFLINE.md) — optional local OpenAI-compatible development model

## Engineering status language

Documentation uses these runtime capability states:

```text
AVAILABLE | EXPERIMENTAL | DEGRADED | DISABLED | MISSING | BROKEN
```

A feature should only be described as complete when it is:

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Experimental systems may have code and deterministic tests while still requiring workstation or production-path validation.

## Safety model

JARVIS is a capability-gated desktop agent, not an unrestricted shell. The controlled self-development target is:

```text
Discover → Propose → Sandbox → Build → Test → Security/Evaluation
→ Diff → Approval → Controlled Release → Post-test → Rollback if required
```

Production self-modification remains disabled by default.

## Legacy documentation

[V6-USER-GUIDE.md](V6-USER-GUIDE.md) is retained for historical behavior. For current development, prefer the V7.7 and V7 documents above.
