# V8 Frontier Execution Plan

Baseline: V7.9 main at `83b7f34b67c0aca444c1139cd7db700364bc554c`.

## Rule
Every phase follows: reproduce → design contract → implement → unit/integration → fault tests → exact-head CI → real-device acceptance when required → update audit evidence.

## Phase 0 — Evidence freeze
This PR only adds audit material. No runtime behavior is changed.

## Phase 1 — Computer/browser truthfulness (P1)
- Wire `ComputerActionEngine` through canonical tool runtime.
- Add target freshness/window identity/secret-field checks.
- Build fixture desktop app and browser form site.
- Add independent postconditions and UNCERTAIN handling.
- Do not promote status until real Windows evidence passes.

## Phase 2 — Background Agent Runtime (P1)
Introduce:
- `BackgroundAgentRuntime`
- `MissionDaemon`
- `BackgroundTaskQueue`
- authenticated IPC bridge
- process heartbeat/restart recovery
- durable queue schema and ownership leases
- resource/account/browser/file locks
- notification interface
UI remains optional client; runtime stays least privilege.

## Phase 3 — Event + workspace layer
- EventEngine for approved file/network/app/timer events.
- FileSystemAgent and ApplicationAgent using existing safe primitives.
- WorkspaceManager with STUDY/CODING/DATA_ANALYTICS/WORK/PERSONAL/CONTENT_CREATION profiles.
- Global hotkey/push-to-talk via explicit OS integration.
- Idempotency keys for event-triggered workflows.

## Phase 4 — Voice isolation + long-run reliability
- Native capture subprocess with heartbeat.
- Reconnect/device-change/sleep-resume tests.
- 100 wake trials per declared condition.
- 8-hour idle/background soak.
- Latency p50/p95 evidence.

## Phase 5 — Evaluation/chaos/performance
- 100+ scenario manifests.
- `tests/chaos/` fault suite.
- RAG relevance benchmark.
- Startup/response/tool/memory/UI/resource metrics.
- No fabricated aggregate score.

## Phase 6 — UI convergence and release hardening
- Unified command center.
- Visible global agent states.
- Branch protection/signing evidence.
- Clean-machine human install/update acceptance.
- Release only after all mandatory gates are evidence-backed.

## PR discipline
One concern per branch. Runtime P1s should not be bundled with cosmetic redesigns. Each PR must list: finding IDs, reproduction, patch, tests, exact commit, remaining limits, rollback.
