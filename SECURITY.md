# Security Policy — JARVIS AI OMEGA V7 / V7.5

JARVIS is designed as a permission/capability-gated desktop agent, not an unrestricted remote shell.

## Secrets

Do not commit or share:

- `.env`
- API keys
- passwords
- OAuth client secrets/tokens
- recovery codes
- SSH/private keys
- banking credentials

Secret-like paths/content are blocked from normal memory/indexing workflows where applicable. Audit and observability records use redaction/hashes rather than raw secret arguments.

If a key is exposed publicly, revoke/rotate it immediately.

## Tool security

Tools have explicit capabilities and risk levels. Unknown/unprofiled tools are denied by default.

Trusted Local Mode may auto-allow ordinary LOW/MEDIUM allowlisted local actions. It does not override `DENY` or `ALWAYS_ASK`, and it does not grant arbitrary shell access, credential scraping or hidden persistence.

High-risk keyboard/mouse/code-write/email-send/calendar-write actions remain stronger security boundaries.

## Browser / prompt injection

Webpage/search content is always untrusted data. It must never replace system/developer/security policy. Browser V2 includes checks for common instruction override, secret extraction, command execution and security-bypass prompt injection patterns.

Public page-reading tools reject obvious local/private literal targets and embedded URL credentials.

## Self-development immutable core

Normal automated self-development MUST NOT modify:

- `jarvis/security/`
- `jarvis/self_development/policies.py`
- `jarvis/self_development/rollback.py`
- `.env` / secret files
- `.git/`
- protected production/runtime data

It must not disable permissions, hide audit evidence, remove secret protection, escape the sandbox or silently enable unrestricted production modification.

## Self-development flow

```text
Gap
→ Proposal
→ Isolated Git worktree
→ Build
→ Compile + full tests
→ Bounded debug
→ Policy/security review
→ Diff/evidence
→ Approval
```

Production activation is a separate controlled release gate.

Safe default:

```env
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
```

## Controlled release

Even an approved proposal cannot deploy by default. The experimental release engine additionally requires deliberate production-self-modification enablement, a clean unchanged production checkout, current tests, reviewed files, immutable-core policy and fast-forward-only deployment.

Rollback uses history-preserving Git revert plus regression verification.

## Backup / restore

Database restore/import is destructive and requires confirmation. JARVIS creates a pre-restore backup and validates SQLite integrity before/after restore.

## Security testing

The V7.5 regression suite includes adversarial cases for:

- prompt injection
- private browser targets
- secret persistence/extraction
- unknown/unrestricted shell tools
- trusted-mode high-risk bypass
- path traversal
- secret-like local paths
- self-development modification of security/rollback controls

Security failures block release readiness.
