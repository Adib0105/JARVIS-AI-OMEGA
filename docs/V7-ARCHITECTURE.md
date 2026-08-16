# JARVIS AI OMEGA V7 / V7.5 — Architecture

**Development branch:** `v7-development`  
**Stable baseline:** V6 on `main`

## Design goal

V7 is a reliability-focused desktop-agent architecture. The central execution rule is:

```text
Intent → Context → Plan → Permission → Action → Observation → Verification
                                         │
                                         └→ Recovery / Replan when needed
```

A successful tool call is not automatically a verified successful outcome.

## High-level architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         USER / UI                           │
│  Desktop HUD • Voice • Chat • Command Center • Attachments │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               CONTEXT + CAPABILITY REGISTRY                │
│ current request • memory context • runtime capability truth │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│            PROVIDER-NEUTRAL AI + MODEL ROUTER              │
│ FAST • SMART • VISION • CODING • PLANNING • REVIEW • LOCAL│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    MISSION ORCHESTRATOR                     │
│ UNDERSTAND → PLAN → EXECUTE → VERIFY → RECOVER / REPLAN   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               CAPABILITY SECURITY + AUDIT                  │
│ risk profiles • Trusted Local Mode • approvals • redaction │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        TOOL LAYER                           │
│ files • docs • browser • computer • coding • git • Google │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             EVIDENCE + MEMORY + OBSERVABILITY              │
│ verification • layered memory • health • latency • usage  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 V7.5 IMPROVEMENT LAYER                     │
│ self-evaluation → gap detection → proposal / skill idea   │
│ → isolated sandbox → build/test/debug/evaluate → diff     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                    AWAITING OPERATOR APPROVAL
                               │
                               ▼
                 CONTROLLED RELEASE / ROLLBACK
```

## 1. Provider layer

Provider-specific behavior lives behind provider-neutral contracts. Core mission logic should not depend directly on one vendor SDK.

Supported architectural routes include:

```text
FAST | SMART | VISION | CODING | PLANNING | REVIEW | SUMMARY | LOCAL
```

The router selects a configured model/provider path while observability records safe success/failure/latency/fallback metadata.

## 2. Mission engine

Missions are persisted and move through explicit states. The mission layer owns:

- goal/plan state
- ordered steps
- tool execution requests
- retry eligibility
- recovery/replanning decisions
- pause/resume/cancel controls
- verification/evidence state
- safe event history

The orchestrator does not expose private chain-of-thought. It stores safe operational summaries and evidence.

See [V7-AGENT.md](V7-AGENT.md).

## 3. Security architecture

The tool runtime is capability-gated. Tool profiles define risk and capabilities such as file read/write, app control, keyboard/mouse control, browser operations, code changes, email or calendar actions.

Key rules:

- unknown/unprofiled tools are denied by default
- explicit deny/always-ask policy wins
- Trusted Local Mode only reduces friction for ordinary allowlisted LOW/MEDIUM local actions
- high-risk actions remain stronger boundaries
- secret-like paths/content are protected
- audit/observability must not store raw credentials

See [V7-SECURITY.md](V7-SECURITY.md) and root [SECURITY.md](../SECURITY.md).

## 4. Tool runtime and verification

Tools produce operational results; verification evaluates whether enough evidence exists to claim the requested effect happened.

Possible evidence states include:

```text
VERIFIED | PARTIAL | FAILED | UNVERIFIED
```

This separation is important for desktop actions, browser interactions and any side effect whose real-world result may differ from the tool call result.

## 5. Computer Use V2

Computer Use follows a semantic-first model:

```text
UI Automation
→ target scoring/confidence
→ ambiguity gate
→ optional OCR fallback when UIA has no confident match
→ action
→ post-action evidence
```

Ambiguous UIA results are never bypassed with OCR guesses. OCR-resolved actions remain PARTIAL until independently verified.

See [V7-COMPUTER-USE.md](V7-COMPUTER-USE.md).

## 6. Browser V2

Browser/page content is untrusted external data.

Public page-reading paths apply URL/trust checks, block obvious local/private literal targets where applicable, reject embedded credentials and scan common prompt-injection patterns.

Webpage instructions cannot replace JARVIS security policy.

See [V7-BROWSER.md](V7-BROWSER.md).

## 7. Memory and context

V7 memory is additive and layered:

- working
- episodic
- semantic
- procedural

The context builder prioritizes the current request over stale memory and uses hybrid retrieval. V7.5 adds lifecycle behavior such as reinforcement, contradiction detection, superseding and confidence/stale decay.

Persistent memory/indexing includes secret-protection boundaries.

See [V7-MEMORY.md](V7-MEMORY.md).

## 8. Documents and RAG

Document ingestion supports common office/text formats. V7.5 adds content-hash provenance so indexing can distinguish:

```text
UNCHANGED | UPDATED | DUPLICATE / SAME CONTENT
```

This avoids unnecessary re-indexing and keeps source metadata explicit.

## 9. Observability and Health

Observability records safe operational metadata such as:

- provider/model
- request success/failure
- latency
- fallback
- token counters when available
- mission/system/self-development events

Cost is only recorded when the provider explicitly reports a numeric cost. Otherwise it remains `N/A`.

The Health System reports PASS/WARNING/FAIL and does not pretend a remote provider is healthy without evidence.

## 10. Self Evaluation and Gap Detection

Self Evaluation derives metrics from persisted mission/audit evidence. Unsupported accuracy metrics remain `N/A` rather than being invented.

Gap Detection combines:

- Capability Registry MISSING/DEGRADED evidence
- measured low scores
- repeated tool failures
- repeated mission blockers

This produces evidence-backed improvement proposals instead of random feature generation.

## 11. Controlled Self Development

The self-development layer is intentionally sandbox-first:

```text
Gap → Proposal → Isolated Git Worktree → Build → Compile/Test
→ Bounded Debug → Security/Evaluation → Diff → AWAITING_APPROVAL
```

Protected security/secret/sandbox/rollback controls are outside ordinary self-modification scope.

Production self-modification is disabled by default.

See [V7-SELF-DEVELOPMENT.md](V7-SELF-DEVELOPMENT.md).

## 12. Skills and workflow learning

Repeated safe workflows can create reusable proposals. Skill generation produces a manifest plus implementation/tests/docs/permission/evaluation metadata in the same isolated development pipeline.

Activation remains a separate gate and requires a deployed linked improvement plus explicit operator activation.

## 13. Backup and restore

Database backup uses SQLite's backup API with integrity checks and SHA-256 manifest metadata.

Restore/import requires explicit destructive confirmation, creates a pre-restore backup and verifies the restored database again.

## 14. Controlled release and rollback

Experimental controlled release requires:

- approved proposal
- deliberate production-self-modification enablement
- fresh tests
- immutable-core policy pass
- exact reviewed files
- clean production checkout
- expected HEAD unchanged
- fast-forward-only deployment

Rollback is history-preserving (`git revert`) plus regression verification, not a destructive force reset.

See [V7-RELEASE.md](V7-RELEASE.md).

## 15. UI composition

The main desktop remains focused on conversation, voice and quick actions. Advanced operational state is separated into the Agent Command Center, which exposes safe mission/health/capability/observability/security/self-development/data/release/skills views without exposing private chain-of-thought.

## Engineering invariant

No subsystem should claim more capability than the runtime can prove.

```text
Capability truth + permission + observable evidence > optimistic agent narration
```
