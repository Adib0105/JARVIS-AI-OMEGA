# Performance Audit — V8 Frontier Baseline

## Findings
| ID | Severity | Location | Problem | Root cause | Impact | Recommended fix | Status | Test required | Verification |
|---|---|---|---|---|---|---|---|---|---|
| PERF-01 | P2 | startup/voice | CI checks launch correctness, but target-PC startup, first-response and wake p50/p95 are not maintained as release metrics. | Functional gates came before performance SLOs. | Regressions can pass while feeling slow. | Add benchmark script with hardware metadata and stored p50/p95. | OPEN | cold/warm launch + 100 wake trials | thresholds declared before run |
| PERF-02 | P2 | background design | Future persistent service risks idle CPU/RAM/mic overhead. | No unified service exists yet. | Battery/resource drain. | Event-driven idle state, lazy OCR/browser/model loading, bounded queues, CPU/memory budgets. | DESIGN | 8h idle soak | stable memory and agreed idle CPU ceiling |
| PERF-03 | P2 | retrieval | Hybrid retrieval supports lexical/sparse + optional embeddings, but large-corpus latency/quality benchmarks are not release gates. | RAG quality framework is partial. | Slow or low-quality retrieval at scale. | Add corpus-size benchmarks with labelled relevance. | OPEN | 1k/10k/100k chunk tests | p95 latency + relevance metrics tracked |
| PERF-04 | P3 | UI | UI responsiveness is not represented as a continuous quantitative metric. | Tk operations are mostly functional tested. | Background refresh may cause jank. | Instrument event-loop stalls and long callbacks. | OPEN | stress refresh | no callback blocks UI beyond agreed budget |
