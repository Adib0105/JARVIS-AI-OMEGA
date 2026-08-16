# JARVIS OMEGA V7 — Agent & Mission Engine

## Status

Phase 2 is implemented on `v7-development` with deterministic unit tests. The V6 `main` branch remains untouched as the stable baseline.

## Mission state machine

V7 persists mission state in additive SQLite tables:

- `v7_missions`
- `v7_mission_events`

Mission states:

```text
IDLE
UNDERSTANDING
PLANNING
WAITING_FOR_PERMISSION
EXECUTING
VERIFYING
RECOVERING
REPLANNING
PAUSED
COMPLETED
FAILED
CANCELLED
```

The current orchestrator records state changes and safe event summaries. It does not expose private chain-of-thought.

## Mission object

A mission stores:

- stable mission ID
- goal/session ID
- timestamps/status
- ordered plan steps
- current step
- completed/failed step IDs
- attempts/retry count
- recovery count
- tool evidence
- per-step verification
- final verification
- final report

Failed steps remain in history. If a later replan successfully replaces a failed step, the old step is marked recovered rather than deleted. Old pending work made obsolete by a replan becomes `SUPERSEDED`.

## Execution rule

V7's target trust flow is:

```text
Intent
  -> Plan
  -> Permission
  -> Action
  -> Verification
  -> Evidence
  -> Report
```

A tool returning without raising an exception is not automatically enough to claim verified success.

## Tool evidence

`RecordingToolRegistry` wraps the existing V6 ToolRegistry without rewriting handlers. It records the tool name, sanitized in-memory arguments, structured tool result, and timestamps for the current agent turn. These events feed step verification.

Persistent audit redaction/capability metadata are Phase 3 responsibilities.

## Verification

`VerificationEngine` distinguishes:

- `VERIFIED` — structured evidence supports the result
- `PARTIAL` — the action was acknowledged but the external/visible state could not be independently observed
- `FAILED` — tool output or postcondition verification failed

Examples:

- safe model-only reasoning: verifies that a model result was produced; no external effect is claimed
- local text write: re-reads the written file and compares expected content
- unit tests: verifies process return code
- Gmail send / Calendar create: records provider-returned IDs as provider acknowledgement
- desktop click/type/app/browser launch: currently `PARTIAL` because V7 cannot yet semantically observe the resulting UI state; stronger semantic UI verification is Phase 5

A final report explicitly names unverified external actions instead of claiming full success.

## Retry rules

Transient retry policies exist for timeout, network, rate-limit, model and vision failures. Retry uses bounded exponential backoff with jitter.

A step containing side-effecting tool evidence is not blindly retried. That prevents duplicate emails, duplicate writes, repeated clicks, and similar unsafe recovery behavior.

Permission denial is never retried or bypassed.

## Replanning

When a non-permission failure cannot be safely retried:

1. preserve completed work
2. preserve failed-step evidence
3. ask the V7 replanner for the smallest safe remaining plan
4. mark obsolete unexecuted steps `SUPERSEDED`
5. execute only the replacement plan
6. mark the original failure `RECOVERED` only if its replacement steps complete

The number of replans is bounded.

## Cancellation and pause/resume

The orchestrator exposes mission-level control events:

- cancel
- pause
- resume

Cancellation prevents subsequent mission steps/retries from starting. It cannot retroactively undo an external action already completed before cancellation.

GUI buttons/timeline wiring for these controls is planned for the product-polish UI phase, while the underlying runtime API exists now.

## Known Phase-2 limitations

- semantic screen/browser post-action verification is not implemented yet
- approval decisions are still V6 broad tool-name prompts until Phase 3 capability permissions
- no distributed/background mission executor; one local runtime owns a mission
- provider requests already in flight cannot always be force-cancelled by Python; cancellation stops future mission work
- Gmail/Calendar provider acknowledgement is recorded, but deeper read-after-write verification will be strengthened later
