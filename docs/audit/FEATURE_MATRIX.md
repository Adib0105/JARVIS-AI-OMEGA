# Feature Matrix — V8

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

Status describes integration/evidence, not the number of classes or imported modules.

| Capability | Status | Evidence / boundary |
|---|---|---|
| Conversation/provider routing | IMPLEMENTED / live provider UNVERIFIED | Provider-neutral core, router, observed provider and circuit breaker; no real account call in this audit. |
| Missions and persistence | PARTIAL | State/versioned storage exists; no durable restart scheduler. V8-003, V8-008, V8-016. |
| Tool security/audit | IMPLEMENTED / reviewed scope only | Central gate and integrity log; full platform/every-route certification is not claimed. |
| Outcome verification | PARTIAL — defects reproduced | V8-001/002/003/006 prevent a verified-autonomy claim. |
| Background wake/tray/sign-in | PARTIAL | Same-process background behavior exists. Independent runtime is missing. V8-007. |
| Background queue/events/notifications | MISSING as unified services | Existing reminders/wake callbacks are not the requested durable engine. V8-008/017/018. |
| Native capture/reconnect | PARTIAL | Thread-bound capture; process isolation and physical matrix missing. V8-011. |
| Voice output/controls | IMPLEMENTED / physical output UNVERIFIED | Speech worker/fallbacks and media controls; audible speaker output was not tested here. |
| Global activation/emergency stop | PARTIAL / MISSING global integration | Tk shortcuts and mission cancellation exist; no central OS-wide stop/hotkey service. V8-012/017. |
| Semantic desktop actions | BLOCKED for end-to-end use | Standalone UIA/OCR; schema/handler, secret/freshness and postcondition gaps. V8-006/009. |
| Public browser research | IMPLEMENTED foundation | Bounded public reader with URL/injection policy; read content is untrusted. |
| Stateful browser/forms | MISSING general workflow | Specialized YouTube automation exists; general form/tab/frame driver does not. V8-010. |
| Files/app/settings | PARTIAL | Approved read/write and allowlisted app/settings actions; bulk file/workspace/Wi-Fi verification incomplete. V8-013/018. |
| Memory lifecycle | PARTIAL | Working/episodic/semantic/procedural memory, conflict/supersede/decay exist; full requested consent/ownership/expiry UX not proven. |
| Document RAG | PARTIAL | PDF/DOCX/XLSX/CSV extraction, content hashes and hybrid retrieval; citations/deletion/quality benchmark gaps. V8-019. |
| Vision/multimodal | PARTIAL | Image/screenshot/provider and document paths; unified video/audio/mission context not demonstrated. |
| CSV/Excel data analyst workflow | MISSING end-to-end agent | Reading a spreadsheet is not a reproducible clean/analyze/chart/report pipeline. |
| Coding/Git inspection and writes | PARTIAL | Inspection and approved writes exist; atomic write and sandbox execution gaps. V8-013/020. |
| Self-development/skills | EXPERIMENTAL / execution BLOCKED | Proposal/worktree/approval pipeline exists; untrusted execution stays disabled. V8-020. |
| Self-evaluation/benchmark | PARTIAL — defects reproduced | Runner and comparison require strict evidence/cohort repair. V8-004/005. |
| Observability and security center | PARTIAL | Recorded tool/model latency, explicit reported cost, audit and views exist; silent panel failures remain. V8-021. |
| Database/backup/restore | IMPLEMENTED foundation / recovery PARTIAL | Closing connections, migrations, backups and integrity checks; hardware/process fault matrix remains open. |
| Accounts/billing/recovery | PARTIAL | 30 service tests pass; HTTPS/SMTP/Stripe test-merchant/live entitlement deployment is not verified. |
| Installer/updater/release | PARTIAL / production BLOCKED | Hosted package/install/update checks passed historically; signing/protection/physical acceptance incomplete. V8-022/023. |
| Requested UI redesign | PENDING | Existing UI is functional foundation; requested visual consolidation follows P1 reliability work. |
