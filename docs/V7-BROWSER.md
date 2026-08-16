# JARVIS AI OMEGA V7 / V7.5 — Browser Agent

## Status

Core browser abstraction is **IMPLEMENTED**. Browser V2 security hardening is **IMPLEMENTED in code and awaiting the final repository-wide quality gate**.

## Current architecture

```text
USER REQUEST
→ URL / SEARCH INTENT
→ DOMAIN / URL TRUST CHECK
→ NAVIGATE OR READ
→ TREAT PAGE AS UNTRUSTED DATA
→ PROMPT-INJECTION SCAN
→ EXTRACT / OBSERVE
→ VERIFY RESULT
```

## Public browser-read trust

Public read/extract paths reject:

- malformed non-HTTP(S) URLs
- embedded URL credentials
- localhost / `.local` hosts
- literal private, loopback, link-local, multicast, reserved or unspecified IP addresses

This reduces accidental access to local/private network targets through public page-reading tools.

## Prompt injection

Webpage text is data, never system/developer instructions.

The Browser V2 scanner flags common patterns such as:

- “ignore previous instructions”
- secret/password/API-key extraction requests
- commands asking the agent to run a shell
- requests to disable permissions/security/audit
- fake role/system-message injections

A flagged page is not automatically trusted just because its HTML/text says it is trusted.

## Navigation verification

Opening a browser process/window is only partial evidence. It does not prove the requested page completely loaded. Read/extract operations can be verified when the public reader actually returns content from the requested URL, but that returned content remains untrusted.

## Important limitation

Browser V2 is not a general unrestricted browser automation engine. High-risk typing/click/submission behavior remains capability-gated and must respect the desktop/computer-use verification policy.
