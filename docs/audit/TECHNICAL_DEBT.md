# Technical Debt — V8 Frontier Baseline

| ID | Severity | Debt | Why it matters | Action |
|---|---|---|---|---|
| TD-01 | P1 | Desktop process owns background wake/lifecycle | Prevents durable autonomous background missions | Extract supervised per-user background host after IPC/security design |
| TD-02 | P1 | Computer/browser autonomy components are not fully integrated | Capability exists in pieces but cannot be truthfully called end-to-end verified | One canonical action/session runtime with postconditions |
| TD-03 | P2 | Legacy/new parallel modules (`core.py/core_v7.py`, `memory.py/memory_v7.py`) | Duplicate mental model and regression surface | Deprecation map + compatibility facade |
| TD-04 | P2 | PyAutoGUI low-level automation remains beside semantic UIA/OCR | Fragile coordinate behavior can bypass higher-level intent if routed poorly | Force central routing; coordinates fallback only |
| TD-05 | P2 | Broad swallowed UI refresh exceptions | Hidden stale operational state | Telemetry + visible degraded state |
| TD-06 | P2 | Benchmark corpus too small | Prevents evidence-based quality claims | 100+ versioned scenarios + real-device evidence |
| TD-07 | P2 | Operational security controls partly source-only | Branch protection/signing/deployment cannot be proven from code | Capture live operational evidence |
| TD-08 | P2 | Real provider/device acceptance is external to CI | Critical runtime paths can remain green in mocks | Dedicated acceptance environment |
