# JARVIS AI OMEGA V7 — Architecture

**Status:** V7 development  
**Version:** 7.0.0-dev foundations  
**Stable baseline:** V6 on `main`

## Design goal

V7 is a reliability-focused evolution of V6. The intended execution rule is:

```text
Intent -> Permission -> Action -> Verification -> Evidence -> Report
```

A successful tool call is not automatically a verified successful outcome.

## Phase 1 — implemented foundation

### Provider abstraction

Provider SDK details now live under:

```text
jarvis/providers/
  base.py
  openrouter_provider.py
  openai_provider.py
  local_provider.py
  factory.py
```

The common interface exposes provider-neutral chat, tool-call turns, continuation, vision and structured-text operations. `jarvis.core.JarvisOmega` remains a stable public import and delegates to the V7 implementation in `core_v7.py`.

The OpenAI adapter uses the Responses API for text/tool workflows and image input, while the OpenRouter adapter uses its OpenAI-compatible Chat Completions interface. The local adapter targets an explicitly configured OpenAI-compatible local server.

### Configuration validation

`jarvis/config_validation.py` returns structured PASS/WARNING/FAIL findings. Fatal provider/model/key/time-limit problems can block runtime initialization with an actionable error. Optional Google configuration can warn without breaking text chat.

`jarvis/config.py` uses defensive integer/float parsing so a malformed optional environment value does not crash module import before diagnostics can run.

### Error taxonomy

`jarvis/errors.py` normalizes failures into categories:

- AUTH_ERROR
- PERMISSION_ERROR
- RATE_LIMIT
- TIMEOUT
- NETWORK_ERROR
- INVALID_INPUT
- TOOL_ERROR
- RESOURCE_NOT_FOUND
- VISION_ERROR
- MODEL_ERROR
- CONFIG_ERROR
- UNKNOWN_ERROR

Phase 2 recovery policies will consume these normalized categories.

### Structured logging

`jarvis/logging_utils.py` now writes rotating JSONL logs with category/event/field structure and secret redaction. API keys, bearer tokens, passwords and common token fields are redacted before log output. Crash reports also pass through text redaction.

The future audit log is intentionally separate from general runtime logs and will be introduced with capability permissions in Phase 3.

## Compatibility boundaries

The following remain intentionally compatible during migration:

- `from jarvis.core import JarvisOmega`
- current GUI and CLI entry points
- current SQLite V6 database schema
- current ToolRegistry/PermissionGate
- current V6 mission method signature
- existing local file/coding/document/Google modules

No V6 user data migration is performed in Phase 1.

## Temporary compatibility debt

`runtime_guard.py` still applies model-quality/identity behavior at application startup. It now routes repair calls through the provider abstraction, but the guard will be replaced by normal V7 model-router/quality services in a later phase.

The V6 mission loop remains available while the persisted V7 mission state machine is built in Phase 2.

## Phase 2 target

Phase 2 introduces:

- Mission dataclass/state machine
- persisted mission state
- orchestrator
- step verification
- retry manager
- failure classifier policies
- recovery engine
- replanning that preserves completed work
- cancellation foundation

## Safety invariants

V7 will not introduce:

- unrestricted shell execution
- credential/password extraction
- arbitrary destructive file deletion
- stealth persistence
- hidden microphone surveillance
- permission bypass
- silent external account actions

The self-improvement subsystem described in the V7 roadmap is deferred until reliability, permissions, auditing, testing and sandbox/rollback foundations exist.
