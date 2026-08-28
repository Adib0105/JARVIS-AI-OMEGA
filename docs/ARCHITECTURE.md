# Architecture

JARVIS AI OMEGA is a Windows-first Python desktop agent. The stable production path is:

```text
desktop_app.py
  → account/first-run gates
  → composed Tk desktop runtime
  → jarvis.core.JarvisOmega
  → provider + mission orchestrator + audited tools
  → verification, memory, observability and recovery
```

The main packages are:

- `jarvis/agent`: persisted mission state, planning, tool execution, verification and recovery.
- `jarvis/providers`: provider-neutral request, routing, deadline, observation and circuit components.
- `jarvis/security`: capability policy, approval, audit and secret controls.
- `jarvis/computer_use`: UIA-first targeting, browser safety, OCR/visual fallback and action verification.
- `jarvis/observability`: health, redacted telemetry and resource samples.
- `jarvis/evaluation`: deterministic behavior/security benchmarks.
- `jarvis/self_development` and `jarvis/skills`: controlled, approval-gated experimental improvement paths.
- `jarvis/storage`, `memory_v7.py` and `memory_lifecycle.py`: additive SQLite persistence and lifecycle controls.

Compatibility modules remain where removing them would break existing callers. They are not treated as independent production architectures. See `docs/V7-ARCHITECTURE.md` and `docs/V8-ENGINEERING-AUDIT.md` for the detailed map and migration rationale.

