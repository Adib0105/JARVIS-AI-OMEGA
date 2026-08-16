# Security Policy — JARVIS AI OMEGA V7 / V7.5

JARVIS is designed as a **capability-gated desktop AI agent**, not an unrestricted remote shell.

Security is part of the architecture: permission checks, secret protection, audit evidence, sandbox boundaries, browser trust rules, verification and rollback controls are expected to survive feature growth.

## Supported development lines

| Branch | Status |
|---|---|
| `main` | Stable V6 baseline |
| `v7-development` | Active V7/V7.5 engineering |

Security fixes for active V7/V7.5 work should normally target `v7-development` first unless a maintainer decides the stable line also needs a patch.

## Reporting a vulnerability

Do **not** publish real API keys, passwords, OAuth tokens, recovery codes, private keys or private user data in a public issue.

A useful security report should include:

- affected branch/commit
- affected feature/tool
- safe reproduction steps
- expected security boundary
- observed bypass/failure
- impact
- whether user interaction/approval is required
- redacted logs or screenshots

If demonstrating a secret-related issue, use fake/test credentials.

## Secrets

Never commit or share:

- `.env`
- API keys
- passwords
- OAuth client secrets/tokens
- recovery codes
- SSH/private keys
- banking credentials
- private runtime databases containing personal data

Secret-like paths/content are blocked from normal memory/indexing workflows where applicable. Audit and observability records use redaction/hashes rather than raw secret arguments.

If a real key is exposed, revoke/rotate it immediately.

## Capability and permission model

Tools have explicit capability/risk profiles. Unknown or unprofiled tools are denied by default.

Trusted Local Mode may auto-allow ordinary LOW/MEDIUM allowlisted local actions. It does not override explicit deny/always-ask policy and does not grant arbitrary shell access, credential scraping, hidden persistence or destructive unrestricted control.

Higher-risk behavior such as keyboard/mouse control, file/code writes, email send and calendar writes remains capability-gated.

## Tool-result verification

A successful function return is not automatically proof of a successful real-world side effect.

Security-relevant workflows should distinguish:

```text
VERIFIED | PARTIAL | FAILED | UNVERIFIED
```

This reduces the chance that an attacker or faulty tool can make JARVIS report a false success.

## Browser and prompt injection

Webpage/search content is always untrusted data.

It must never replace system, developer or security policy. Browser V2 includes checks for common instruction-override, secret-extraction, command-execution and security-bypass prompt patterns.

Public page-reading paths reject obvious local/private literal targets and embedded URL credentials where applicable.

Examples of untrusted webpage instructions include attempts to:

- ignore previous instructions
- reveal API keys or tokens
- open local credential files
- run shell commands
- disable approval/security policy
- persist hidden instructions into memory

## Local file and memory safety

Normal local tools should respect approved roots/path policy and secret-like path/content detection.

Persistent memory/indexing must not become a route for storing credentials or hidden prompt-injection payloads.

## Computer-use safety

Computer Use V2 follows:

```text
UI Automation → confidence/ambiguity gate → optional OCR fallback
→ action → observation → verification
```

Security rules:

- low-confidence targets stop instead of guessing
- ambiguous UIA results are not bypassed with OCR guesses
- OCR-resolved actions are not falsely promoted to VERIFIED without independent evidence
- raw coordinates are not the primary targeting strategy
- permission gates remain in effect for higher-risk actions

## Self-development immutable core

Normal automated self-development MUST NOT modify protected security-critical areas such as:

- `jarvis/security/`
- self-development policy/guardrail controls
- rollback/release protection logic
- `.env` / secret files
- `.git/`
- protected production/runtime data

Self-development must not:

- disable permissions
- hide audit evidence
- remove secret protection
- escape the sandbox
- silently enable unrestricted production modification
- weaken release/rollback gates to approve its own changes

## Controlled self-development flow

```text
Gap
→ Proposal
→ Isolated Git worktree
→ Build
→ Compile + full tests
→ Bounded debug
→ Policy/security review
→ Evaluation + diff/evidence
→ Approval
```

Production activation is a separate controlled release gate.

Safe defaults:

```env
SELF_DEVELOPMENT_ENABLED=true
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
AUTO_ROLLBACK_ENABLED=false
```

`APPROVED` does not mean `DEPLOYED`.

## Controlled release and rollback

Even an approved proposal cannot deploy by default.

The experimental release engine additionally requires deliberate production-self-modification enablement, a clean unchanged production checkout, current tests, reviewed files, immutable-core policy and fast-forward-only deployment.

Rollback uses history-preserving Git revert plus regression verification rather than destructive `reset --hard` workflows.

## Backup / restore safety

Database restore/import is destructive and requires explicit confirmation. JARVIS creates a pre-restore backup and validates SQLite integrity before/after restore.

Portable builds/exports must not intentionally bundle `.env`, live private databases, API keys or Google OAuth credential/token files.

## Security testing

The V7.5 regression suite includes adversarial coverage for:

- prompt injection
- private/local browser targets
- secret persistence/extraction
- unknown/unrestricted shell tools
- Trusted Local Mode high-risk bypass attempts
- path traversal
- secret-like local paths
- self-development sandbox escape
- self-development modification of protected security/rollback controls
- release/rollback guard behavior

Security failures block release readiness.

## Contribution requirements

Security-sensitive changes should include deterministic regression tests and update relevant documentation. Do not weaken or skip tests to make CI pass.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/V7-SECURITY.md](docs/V7-SECURITY.md).
