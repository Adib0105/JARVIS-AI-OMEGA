# Agent Audit — V8 Frontier Baseline

## Existing agent foundation
- `jarvis/agent/mission.py`: explicit mission/step states.
- `jarvis/agent/orchestrator.py`: persisted state machine, pause/resume/cancel, recovery/replanning.
- `jarvis/agent/tool_runtime.py`: permission-aware recorded execution.
- `jarvis/agent/verification.py`: separates dispatch/acknowledgement from verified outcomes.
- `jarvis/agent/recovery.py`: bounded retry policies.
- `jarvis/capability_registry.py`: runtime availability/degraded/missing states.

## Findings
| ID | Severity | Location | Problem | Root cause | Impact | Recommended fix | Status | Test required | Verification |
|---|---|---|---|---|---|---|---|---|---|
| AG-01 | P1 | multi-mission/background | Mission engine is first-class, but no dedicated concurrent background scheduler/queue with resource locks is present. | V7 focused on correctness before autonomy. | Requested multi-mission agent cannot safely arbitrate resources. | Add scheduler with folder/browser/account/device locks and priority/dependency graph. | OPEN | conflict tests | conflicting missions serialize; independent ones parallelize |
| AG-02 | P2 | planning contracts | Current orchestration is structured but V8's requested explicit planner schema should become a public operational contract. | Planning evolved before the full V8 schema. | Harder to inspect assumptions/dependencies/fallbacks consistently. | Normalize plan object with assumptions, constraints, dependencies, risks, verification/fallback plans. | PARTIAL | schema/round-trip tests | every mission persists normalized plan |
| AG-03 | P2 | learning/evaluation | Verified outcomes are separated from tool transport success, but broad real-world quality feedback remains limited. | Most evaluation is deterministic software evidence. | Adaptive behavior may overfit synthetic signals. | Only learn from verified outcomes; add labelled real-device benchmark corpus. | PARTIAL | benchmark provenance tests | no unverified action becomes positive signal |
| AG-04 | P2 | capability health | Registry is strong, but last_verified/success-rate health should be driven by evidence rather than static/import checks. | Some capabilities still rely on dependency/config state. | AVAILABLE may not equal currently usable on target PC. | Feed live probes + benchmark evidence into health with expiry. | PARTIAL | stale-health tests | device/provider loss degrades status automatically |
