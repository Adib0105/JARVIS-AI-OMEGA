# JARVIS AI OMEGA — Browser Agent 3.0

## Current status

Browser Agent 3.0 is implemented at the repository/runtime level for safe public navigation, reading, extraction, page fingerprints/change checks and bounded multi-source research. Final readiness still depends on the exact-head CI gate and real Windows/browser E2E where applicable.

It is **not** described as unrestricted DOM automation or as a browser-profile/session extractor.

## Architecture

```text
USER REQUEST
→ URL / SEARCH / RESEARCH INTENT
→ URL SYNTAX + CREDENTIAL CHECK
→ DNS RESOLUTION (FAIL CLOSED)
→ REQUIRE EVERY DNS ANSWER TO BE PUBLIC
→ PIN CONNECTION TO A VALIDATED NUMERIC ADDRESS
→ HTTPS HOSTNAME/SNI CERTIFICATE VERIFICATION
→ MANUAL BOUNDED REDIRECT HANDLING
→ REVALIDATE + REPIN EVERY REDIRECT HOP
→ READ AS UNTRUSTED DATA
→ PROMPT-INJECTION SCAN
→ EXTRACT / FINGERPRINT / GATHER EVIDENCE
→ EXPLICIT VERIFICATION STATUS
```

## DNS and redirect boundary

Public browser-read/navigation policy rejects:

- malformed non-HTTP(S) URLs
- embedded URL credentials
- localhost and `.local` hosts
- literal private, loopback, link-local, multicast, reserved or unspecified addresses
- hostnames that fail DNS resolution
- hostnames with any private/non-public DNS answer, including mixed public/private answers
- redirects to private/non-public targets
- HTTPS-to-HTTP redirect downgrades in the controlled reader
- redirect chains beyond the bounded limit

The controlled page reader connects to an address that was already validated instead of performing a second hostname lookup at connection time. HTTPS still validates the original hostname using TLS SNI/certificate verification.

This closes the public-reader DNS-rebinding/redirect class that literal-IP checks alone cannot close.

## Prompt-injection isolation

Returned webpage/search text is always treated as untrusted data. The scanner flags common instruction-override, secret-extraction, shell-command, security-bypass and fake-role patterns.

A prompt-injection flag is evidence about page content; it does not become an instruction to JARVIS and it does not weaken the permission policy.

## Main runtime tools

Public web mode exposes:

- `search_web`
- `search_news`
- `read_web_page`
- `browser_trust`
- `browser_read_safe`
- `browser_extract_safe`
- `browser_snapshot`
- `browser_changed`
- `browser_research`

Desktop/browser-control mode keeps `open_url` and `browser_search`, but those routes now use `BrowserAgent` DNS validation before asking the default browser to navigate.

## Page fingerprints and change detection

`browser_snapshot` safely reads bounded public page text and returns a SHA-256 fingerprint. `browser_changed` accepts a prior valid SHA-256 digest, performs a fresh safe read and reports whether the content fingerprint changed.

A verified fingerprint comparison means the fresh fetched text differs or matches; it does **not** mean the webpage's factual claims are true.

## Bounded research

`browser_research` performs a bounded public search and safely reads a limited number of unique result pages. Per-page content remains untrusted and prompt-injection-scanned.

The overall research evidence deliberately remains `PARTIAL`: successfully gathering multiple sources is not the same as independently proving their factual claims. Source failures are retained as failures instead of being hidden.

## Navigation verification

Opening/searching through the user's default browser returns process-level evidence only. Browser process detection cannot prove the requested page fully loaded, so navigation remains `PARTIAL` unless stronger observable evidence exists.

Controlled public `read`/`extract`/`snapshot` operations can be `VERIFIED` for the transport/read/fingerprint operation because the safe reader actually returned content. The page's content is still untrusted.

## Tool-result truthfulness

Browser methods that return `ok: false` are passed through the main ToolRegistry as failures. They are not nested inside a misleading outer `ok: true` envelope.

## Security capabilities

Read-only browser/research tools use `WEB_READ` / `BROWSER_READ`. Navigation uses `BROWSER_CONTROL`. Browser-related keyboard/mouse/form actions remain governed by the separate high-risk Computer Use capability gates.

## What Browser Agent 3.0 does not currently claim

- arbitrary DOM execution
- silent JavaScript injection
- extracting cookies/passwords/login tokens from browser profiles
- guaranteed multi-tab DOM awareness
- automatic CAPTCHA bypass
- verified form submission without observable post-action evidence
- unrestricted file downloads

Visible browser controls can still be targeted through Computer Use 3.0 when UIA/OCR can identify them confidently. DOM/session-level functionality should only be added later through an explicit, security-reviewed browser integration rather than by weakening the current public-network boundary.
