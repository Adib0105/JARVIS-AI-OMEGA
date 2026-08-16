# JARVIS OMEGA V7 — Security Model

## Principle

V7 treats local/external actions as capabilities, not as a single broad “computer access” switch.

The desired trust flow is:

```text
Intent -> Capability policy -> Approval -> Action -> Verification -> Audit evidence -> Report
```

## Capability policies

Each registered tool has:

- risk level
- required capabilities
- why the capability is needed
- side-effect classification

Policies are configurable through `.env` using:

```text
PERMISSION_<CAPABILITY>=allow|ask|always_ask|deny
```

Examples:

```env
PERMISSION_FILE_READ=allow
PERMISSION_FILE_WRITE=ask
PERMISSION_KEYBOARD_CONTROL=ask
PERMISSION_EMAIL_SEND=always_ask
PERMISSION_CALENDAR_WRITE=always_ask
```

`always_ask` cannot be converted into a session-wide grant.

Unknown/unprofiled tools are denied by default.

## Approval Center

When an `ask` or `always_ask` capability is required, the V7 desktop Approval Center shows:

- action/tool name
- target
- risk level
- reason
- required capabilities
- sanitized argument summary

Decisions:

- ALLOW ONCE
- ALLOW FOR SESSION
- DENY
- CANCEL MISSION

The old boolean confirmation callback remains compatible for terminal/tests, but the V7 desktop uses the richer decision model.

## Audit log

Tool actions are written to an additive SQLite table `v7_audit_log`.

Recorded fields include:

- timestamp
- mission/session IDs
- redacted user-request summary
- tool
- risk level
- capabilities
- SHA-256 hash of sanitized arguments
- approval status
- execution status
- normalized error category
- latency
- provider/model
- verification result

Raw tool arguments are not persisted in the audit table.

The desktop Audit Viewer can filter by execution status, high risk, tool and mission. `Ctrl+Shift+A` is also bound to the viewer.

## Secret protection

Persistent memory input is checked for obvious secret patterns including:

- API keys
- bearer tokens
- OAuth/access/refresh tokens
- password/passcode assignments
- private-key blocks
- recovery/backup codes

V7 refuses to persist secret-like values through memory/note/todo/reminder tools.

General JSON runtime logs and crash reports use a separate redaction layer for secret-like values and common secret field names.

Document/knowledge indexing will receive deeper chunk-level secret filtering in the V7 memory/document phase before it is considered complete.

## Tool safety examples

- `get_current_time`: LOW / SYSTEM_READ / auto-allowed by default
- `read_local_text_file`: MEDIUM / FILE_READ / allowed by default inside existing safe roots
- `write_local_text_file`: HIGH / FILE_WRITE + CODE_WRITE / asks
- `type_text`: HIGH / KEYBOARD_CONTROL / asks
- `gmail_send`: HIGH / EMAIL_SEND / always asks
- `calendar_create`: HIGH / CALENDAR_WRITE / always asks

Existing file-root restrictions, secret-like path blocking, allowlisted app/keyboard actions and lack of arbitrary shell execution remain in place.

## Mission safety

Permission denial stops the affected mission path. V7 does not replan around a denied permission.

Side-effecting actions are not blindly retried by the recovery engine.

`CANCEL MISSION` stops future mission steps; it cannot undo a side effect that already completed before cancellation.

## Immutable future self-improvement boundary

Normal self-improvement logic will not be authorized to weaken or automatically rewrite:

- capability policy
- approval system
- secret handling
- audit logging
- sandbox boundary
- rollback mechanism
- production activation policy

Any future change to those components requires explicit human approval and full security/regression testing.

## Known limitations

- Screen/browser semantic verification is not yet implemented, so some approved UI actions remain explicitly PARTIAL/unverified.
- Audit argument hashes provide correlation/evidence, not reversible raw values.
- Pattern-based secret detection cannot recognize every possible secret format; it supplements rather than replaces careful user behavior.
- Capability settings UI editing is planned for product-polish; `.env` configuration is available now.
