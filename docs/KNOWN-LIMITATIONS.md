# Known limitations

The current hardening work is partial. No F01–F22 finding is marked CLOSED; see [the full matrix](FINAL-HARDENING-AUDIT.md).

- Autonomous generated/project test execution is unavailable. No supported Windows OS isolation backend has been validated; host fallback is denied.
- Auto-updater rollback, global mission budgets, distributed mission ownership and restart-safe side-effect deduplication are missing.
- Browser integration, all-store redaction, all-route capability enforcement, all-reader limits and complete evidence-preserving rendering remain incompletely verified.
- Config save/apply is serialized only inside one process. Other settings writers and stale/cross-process edits can still conflict; no unified precedence model is claimed.
- The source batch launchers permit first run without `.env`; that path still needs an on-PC validation.
- Dependency reproducibility, repository-wide exception classification, remote required checks and real Windows voice/rollback evidence remain outstanding.
- Automatic release publication is disabled. Existing CI packaging checks remain enabled, but no local Windows/package result is available.

Human review of proposed changes can continue. Do not enable unsafe execution or represent this branch as production ready to work around these limitations.
