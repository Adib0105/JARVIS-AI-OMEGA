# Security hardening status

This build is NOT READY FOR RELEASE. See [the evidence matrix](FINAL-HARDENING-AUDIT.md) before interpreting test results.

Generated Python and project-test execution fail closed with `EXECUTION_ISOLATION_UNAVAILABLE`. A worktree is not an OS sandbox. Normal user approval does not enable a host execution fallback. No Windows isolation backend is claimed. The repository's reviewed engineering tests can run in CI; the application's autonomous execution paths remain blocked.

Generated edits cannot alter the enumerated security/control-plane paths, CI, installer scripts or selected adversarial tests. This is a partial trust-base control, not proof that arbitrary generated code is safe.

The public text reader validates every DNS answer, connects to a validated numeric address, retains TLS hostname verification and validates every redirect. This does not establish the security of interactive browser navigation or downloads.

Shared redaction covers tested conversation, mission and logging writes. Do not intentionally store secrets in chat: unknown formats, other stores, old records and exports have not received a complete audit. Redaction is not an encryption or secret-storage mechanism.

Unknown side effects must not be presented as verified. Current fixes remove specific false positives; end-to-end postcondition and concurrency coverage remains incomplete. The updater still lacks proven transactional rollback. Automatic publication is blocked pending closure and Windows evidence.
