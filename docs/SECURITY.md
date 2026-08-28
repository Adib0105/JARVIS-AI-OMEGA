# Security Model

The authoritative action boundary is:

```text
request → capability/risk classification → permission/approval
→ execution → independent verification when possible → redacted audit
```

Security invariants:

- unknown tools fail closed;
- high-risk actions are never silently auto-approved;
- webpage content is untrusted data, not instruction authority;
- private/local browser targets, traversal and unsafe file paths are blocked;
- secrets are rejected from persistent memory and redacted from logs/telemetry;
- password and recovery material is stored as salted PBKDF2-HMAC-SHA256 hashes;
- successful password recovery consumes the recovery code to prevent replay;
- self-development cannot modify protected security/release boundaries through the ordinary generated-change path;
- production self-modification remains disabled by default.

This model does not replace OS account security, filesystem permissions, signed releases or protected Git branches. See `SECURITY.md`, `docs/V7-SECURITY.md` and `docs/V7-SELF-DEVELOPMENT.md` for detailed boundaries and reporting.

