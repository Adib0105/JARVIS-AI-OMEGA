# Security Audit — V8 Frontier Baseline

Baseline: `main@83b7f34b67c0aca444c1139cd7db700364bc554c`.

## Strengths already present
- Capability/permission gates, approval UI and audit events.
- Prompt-injection scanning for public browser content.
- Redaction/secrets modules and blocked generated production self-modification.
- Pinned GitHub Actions, dependency auditing, Defender package/installer checks.
- Billing idempotency/recovery and DPAPI-backed remembered-device support.

## Findings
| ID | Severity | Location | Problem | Root cause | Impact | Recommended fix | Status | Test required | Verification |
|---|---|---|---|---|---|---|---|---|---|
| SEC-01 | P1 | browser/computer-use integration | Password/sensitive-field protection is not yet proven across a live semantic browser/UI workflow. | JH18 is intentionally blocked pending wiring. | Sensitive data could be typed into an unintended target if promoted too early. | Add field classification, secret firewall, origin binding and pre-submit review. | OPEN | malicious/ambiguous form tests | secret never leaves approved origin/field |
| SEC-02 | P1 | background runtime (planned) | A future persistent agent creates IPC/local-command attack surface. | No dedicated service exists yet. | Spoofed local commands or privilege escalation. | Authenticated IPC, per-user identity, least privilege, nonce/replay protection, explicit admin boundary. | OPEN | IPC spoof/replay/fuzz tests | forged client cannot dispatch actions |
| SEC-03 | P2 | `docs/KNOWN-LIMITATIONS.md` | All-route capability enforcement, all-store redaction and all-reader limits remain incompletely verified. | Security controls were added incrementally across many legacy paths. | A bypass may survive in an old path. | Build enforcement matrix and negative tests for every registered tool/reader/store. | OPEN | route inventory test | 100% registered side effects pass central gate |
| SEC-04 | P2 | branch protection/signing | Repository contains a branch-protection template and signing script, but enforcement is not established by source alone. | Operational GitHub/Windows settings live outside code. | Release governance can differ from intended policy. | Apply required checks/review protection and Authenticode signing operationally; capture evidence. | UNVERIFIED | repo/release ops check | live settings + signed artifact chain |
| SEC-05 | P2 | external providers | Live provider, SMTP, Stripe and commercial weather acceptance are not proven on deployed production credentials. | CI intentionally avoids real secrets/charges. | Runtime auth/recovery defects may remain. | Use dedicated test accounts and short-lived credentials in a controlled acceptance environment. | OPEN | live failure/recovery tests | exact-commit evidence with secret-safe logs |
