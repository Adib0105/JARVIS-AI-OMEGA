# JARVIS AI OMEGA V7 / V7.5 — Agent & Mission Engine

## Purpose

The V7 mission engine turns a user goal into an auditable, recoverable sequence of actions with explicit verification.

The target behavior is:

```text
CREATED → PLANNING → AWAITING_PERMISSION → EXECUTING → VERIFYING
                                           │             │
                                           │             └→ RECOVERING / REPLANNING
                                           ▼
                         COMPLETED / PARTIAL / FAILED / CANCELLED
```

A mission should not report success merely because a tool returned without raising an exception.

## Mission state machine

Mission state is persisted in additive SQLite storage. Core states include:

```text
CREATED
PLANNING
AWAITING_PERMISSION
EXECUTING
VERIFYING
RECOVERING
REPLANNING
PAUSED
COMPLETED
PARTIAL
FAILED
CANCELLED
```

Only explicitly legal transitions are accepted. State and its event are stored in one transaction, and an optimistic revision prevents a stale process from overwriting newer mission state. Legacy persisted state names are migrated on load without deleting mission history. Safe event summaries are recorded without exposing private chain-of-thought.

## Mission data

A mission can track:

- stable mission ID
- session ID / user goal
- created/updated timestamps
- current status
- ordered plan steps
- step status and attempts
- safe tool/event summaries
- verification evidence
- retry/recovery/replan history
- pause/cancel control state

## Planning

Planning should produce bounded, actionable steps rather than one giant opaque action.

A useful plan separates:

1. understanding the goal;
2. reading/observing required state;
3. requesting permission when needed;
4. executing a specific action;
5. verifying the result;
6. recovering or replanning when evidence is insufficient.

## Tool execution

Tool calls run through the capability/security layer. The mission orchestrator does not bypass tool risk policy.

Typical flow:

```text
mission step
→ tool profile / capabilities
→ permission decision
→ execute
→ safe tool result
→ verifier
→ evidence state
```

## Verification

Verification can classify outcomes as:

```text
VERIFIED | PARTIAL | FAILED | UNVERIFIED
```

Examples:

- opening an app can be VERIFIED if post-action observation shows the target window;
- typing can be PARTIAL when the action occurred but field readback is unavailable;
- an OCR-targeted click remains PARTIAL until the higher-level outcome is independently observed;
- a failed or denied permission is not retried as if it were a transient error.

Explicit verification evidence from a tool is preserved rather than overwritten by an optimistic default.

## Retry policy

Retries are bounded and depend on error type and side-effect risk.

Transient read-only failures such as selected timeouts may be retried. Permission denials and non-retryable validation/security failures stop instead of repeatedly attempting the action.

## Recovery and replanning

Recovery attempts to repair the current step without pretending the original action succeeded.

Replanning can:

- preserve the failure history;
- supersede obsolete pending steps;
- create a revised plan from current evidence;
- continue only when the new plan is valid and permission policy allows it.

Failure history remains part of the mission record.

## Pause / resume / cancel

Missions support control flags for:

```text
PAUSE
RESUME
CANCEL
```

A paused mission should not silently continue side-effecting work. A cancelled mission becomes terminal unless a new mission is intentionally created.

## Capability Registry integration

The agent receives runtime capability truth instead of assuming every documented feature is available.

Capability states include:

```text
AVAILABLE | EXPERIMENTAL | DEGRADED | DISABLED | MISSING | BROKEN
```

This helps avoid false claims such as promising microphone/OCR/local-model behavior when the dependency or configuration is unavailable.

## Context and memory

The agent context builder combines the current request with bounded relevant memory. Current user intent has priority over stale memory.

The mission layer can use working/episodic/semantic/procedural memory without turning old retrieved text into higher-priority instructions.

## Browser and external-content isolation

Web/search/page content is untrusted data. Browser content cannot replace the mission's security/system rules.

Prompt-like text inside a webpage is evidence/data to analyze, not an instruction to reveal secrets, run commands or disable permissions.

## Computer Use V2 integration

For semantic desktop actions:

```text
observe controls
→ score target
→ confidence / ambiguity gate
→ optional OCR fallback when appropriate
→ permission
→ action
→ post-action observation
→ verification
```

Low-confidence or ambiguous targeting stops safely rather than guessing.

## Observability

The mission engine can feed safe operational events to observability, including:

- mission status/outcome
- latency
- retries/recovery/replans
- provider/model path
- tool failures
- verification state

Raw credentials and private chain-of-thought are not observability payloads.

## Self Evaluation integration

V7.5 self-evaluation derives metrics from persisted evidence such as mission outcomes, verification rates, recovery behavior, retries, tool success/failure and latency.

Unsupported metrics remain `N/A` instead of being guessed.

Capability Gap Detection can then use repeated failures/blockers and low measured performance to create improvement proposals.

## Controlled self-development relationship

The mission engine may identify or feed an improvement opportunity, but production source code is not rewritten directly from a normal mission.

Improvement lifecycle:

```text
measured gap → proposal → isolated sandbox → build/test/debug/evaluate
→ diff → approval → controlled release
```

See [V7-SELF-DEVELOPMENT.md](V7-SELF-DEVELOPMENT.md).

## Operator UI

The Agent Command Center can expose safe mission information such as:

- current state
- plan steps
- verification status
- failures/retries
- pause/resume/cancel controls
- health/capability context

It should not expose hidden chain-of-thought.

## Invariant

The mission engine optimizes for **reliable completion with evidence**, not maximum action count.
