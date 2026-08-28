# JARVIS AI OMEGA V7 / V7.5 — Tools

## Tool runtime principles

JARVIS tools are not arbitrary shell access. Each registered tool has a capability/risk profile and runs through the V7 capability permission gate plus audit evidence.

Typical capabilities include:

- SYSTEM_READ
- MEMORY_READ / MEMORY_WRITE
- FILE_READ / FILE_WRITE
- DOCUMENT_READ
- WEB_READ
- BROWSER_READ / BROWSER_CONTROL
- APP_CONTROL
- SCREEN_READ / SCREEN_CONTROL
- KEYBOARD_CONTROL / MOUSE_CONTROL
- CODE_READ / CODE_WRITE / CODE_TEST
- GIT_READ
- EMAIL_READ / EMAIL_SEND
- CALENDAR_READ / CALENDAR_WRITE

Unknown/unprofiled tools are denied by default.

`ToolRegistry.security_contracts()` exposes one machine-readable contract for every registered tool. Each contract includes strict allowed inputs, capability ID, risk level, required permissions, allowed resources, side effects, approval requirement, verification requirement and audit requirement. Tests fail if an exposed tool lacks this metadata.

## Trusted Local Mode

`TRUSTED_LOCAL_MODE=true` removes repetitive approval popups for ordinary LOW/MEDIUM allowlisted local actions such as opening an allowlisted app, browser search, approved file/document reads, code-tree inspection, tests and Git read operations.

It does **not** turn JARVIS into unrestricted local execution. High-risk keyboard/mouse actions, code/file writes, email send and calendar writes remain capability-gated. Secret-path and approved-root restrictions remain active.

## Current tool families

- system/time/telemetry
- memory/search/notes/todos/reminders
- public web/news/page reading
- local file search/read/index
- PDF/DOCX/XLSX/CSV/TXT/MD document extraction/indexing
- allowlisted app/URL opening
- browser search
- desktop keyboard/mouse actions
- coding project inspection/write/test
- Git status/diff/log
- optional Gmail/Calendar
- image/screen vision through dedicated UI/runtime paths

## Audit

V7 audit stores security-relevant metadata, hashes and redacted summaries rather than raw secrets/tool argument payloads. Observability is a separate higher-level telemetry layer and likewise must not store prompts, passwords, API keys or OAuth tokens.

## Tool result and verification states

A tool execution is recorded as:

```text
SUCCESS | PARTIAL | FAILED | DENIED | TIMEOUT | CANCELLED | UNVERIFIED
```

A successful execution is not automatically proof of the real-world side effect. Mission/computer-use verification separately classifies evidence as `VERIFIED`, `PARTIAL`, `FAILED` or `UNVERIFIED` depending on what can independently be observed.
