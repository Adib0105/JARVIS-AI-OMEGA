# JARVIS AI OMEGA V7 / V7.5 — Browser Agent

## Status

Core browser abstraction and protected page-reader hardening are **IMPLEMENTED and deterministically tested**. Cross-platform CI for the current hardening branch and live default-browser behavior are still separate gates.

## Current architecture

```text
USER REQUEST
→ URL / SEARCH INTENT
→ URL + DNS TRUST CHECK
→ CONNECT TO VALIDATED PUBLIC ADDRESS
→ REVALIDATE EVERY REDIRECT
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
- DNS names with any private, loopback, link-local, reserved or otherwise non-global answer
- redirect hops that leave the public HTTP(S) boundary
- control characters, invalid ports and oversized URLs
- oversized responses and unsupported response content types

The protected reader connects to a validated address while preserving the original hostname for the HTTP `Host` header, TLS SNI and certificate validation. This narrows DNS-rebinding exposure. HTML extraction excludes active/non-content elements such as scripts, styles, templates and SVG.

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

Browser V2 is not a general unrestricted browser automation engine. High-risk typing/click/submission behavior remains capability-gated and must respect the desktop/computer-use verification policy. Opening a URL in the user's default external browser is permission-gated but that external browser owns its subsequent network redirects; the in-process public reader's address pinning cannot govern another process.
