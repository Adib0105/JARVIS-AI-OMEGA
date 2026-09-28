# Feature Matrix — V8 Frontier Baseline

Status meanings: AVAILABLE = implemented with meaningful software evidence; PARTIAL = foundation exists but acceptance/integration gap remains; MISSING = requested first-class capability not present; BLOCKED = intentionally not promoted without required evidence.

| Capability | Status | Evidence / note |
|---|---|---|
| Mission state machine | AVAILABLE | `jarvis/agent/mission.py`, orchestrator + persistence |
| Pause/resume/cancel/recovery/replan | AVAILABLE | `jarvis/agent/orchestrator.py` |
| Tool permission/audit runtime | AVAILABLE | `jarvis/agent/tool_runtime.py`, security modules |
| Verification engine | AVAILABLE | distinguishes VERIFIED/PARTIAL/UNVERIFIED/FAILED |
| Capability registry | AVAILABLE | runtime dependency/config status |
| Provider abstraction/circuit breaker | AVAILABLE | `jarvis/providers/` |
| Layered memory lifecycle | PARTIAL | contradiction/supersede/decay present; full V8 taxonomy/provenance UX needs expansion |
| Hybrid RAG | PARTIAL | document index + BM25/sparse + optional embeddings; broader ingestion/citation benchmarks needed |
| Coding agent | AVAILABLE/PARTIAL | coding tools/agent exist; production self-modification remains blocked by design |
| Self-evaluation | AVAILABLE/PARTIAL | engine + benchmark storage exist; broad 100+ corpus missing |
| Self-development | PARTIAL | proposal/sandbox/testing pipeline exists; unrestricted production execution intentionally blocked |
| Observability/security center | AVAILABLE/PARTIAL | core data + command-center surfaces exist; broader unified telemetry UI planned |
| Voice/wake | PARTIAL | local background wake + recovery; physical device/full-duplex/isolation gaps remain |
| Semantic computer use | BLOCKED | UIA/OCR engine exists; JH18 live integration/verification remains open |
| Stateful browser agent | PARTIAL | open/read/search/extract available; full click/type/form/tab/frame session missing |
| Persistent background OS agent | MISSING | no unified service/daemon outside desktop lifecycle |
| Background task queue | MISSING | no first-class durable priority/dependency queue |
| Event engine | MISSING | no unified OS/file/network/window event bus matching requested model |
| FileSystemAgent | MISSING as first-class agent | file tools exist, but no dedicated semantic file-agent workflow layer |
| ApplicationAgent | MISSING as first-class agent | Windows/app controls exist, but no unified launch/focus/inspect/restart agent |
| Global hotkey activation | MISSING | no repository evidence found |
| WorkspaceManager profiles | MISSING | no first-class STUDY/CODING/DATA ANALYTICS profile manager found |
| Mission notifications | PARTIAL | desktop/tray/background UI pieces exist; unified durable notification manager absent |
| Account/subscription backend | PARTIAL | service + billing recovery implemented; live merchant/SMTP deployment pending |
