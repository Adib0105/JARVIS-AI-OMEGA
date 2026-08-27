# Contributing to JARVIS AI OMEGA

JARVIS AI OMEGA prioritizes reliability, verification, security, clear evidence and focused changes over feature count.

## Branch strategy

- `v7-development` — active engineering/release-candidate branch.
- `main` — separate stable line; do not infer its version from historical branch names.

The application version is defined only by `jarvis.version.APP_VERSION`. Do not add hard-coded release versions to runtime, setup, diagnostics, packaging, installer or CI files.

## Before you start

1. Search existing issues and documentation.
2. Read `README.md`, `SECURITY.md` and the relevant subsystem docs.
3. Keep changes narrow enough to review and verify.
4. Do not overwrite local work without checking `git status`.

## Windows development setup

```powershell
git fetch origin
git switch v7-development
git pull origin v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

For packaging work:

```powershell
.\setup_windows.ps1 -IncludeBuildTools
```

The setup script uses the checked-in release constraints and exact direct pins. See `docs/DEPENDENCIES.md` and `docs/V7-SETUP.md`.

## Quality gate

Before opening a pull request:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`self_check_v75.py` exists only as a backward-compatible wrapper.

Do not delete, skip, weaken or falsify a regression test to make CI green. Fix the root cause or document a genuine unsupported limitation.

## Engineering rule

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

A successful import, API call or OS input event is not automatically proof that the requested real-world effect happened. Add observable verification whenever practical and preserve `NOT_TESTED` / `NOT VERIFIED` when evidence does not exist.

## Security rules

Never commit `.env`, API keys, passwords, OAuth secrets/tokens, recovery codes, SSH/private keys, live private databases or credential exports.

New tools must be narrow, capability-profiled, auditable and permission-aware. Unknown/unprofiled tools must fail closed.

Do not add unrestricted arbitrary shell execution, credential scraping, hidden persistence, permission/audit bypasses, or self-development paths that rewrite protected security/secret/sandbox/rollback controls.

Web/search/page content remains untrusted data.

## Computer-use changes

Preserve the reliability model:

```text
semantic target → confidence/ambiguity gate → action → observation → verification
```

Low-confidence or ambiguous targets should stop safely rather than guess. Coordinate clicking must not become the default targeting strategy.

## Self-development changes

Controlled self-development remains sandbox-first:

```text
Gap → Proposal → Isolated Worktree → Build → Tests → Security/Evaluation
→ Diff → Approval → Controlled Release
```

`APPROVED` must not silently become `DEPLOYED`, and production self-modification remains disabled by default.

## Tests

Add or update deterministic tests when behavior changes. Prefer externally observable contracts over implementation trivia.

Important areas include mission verification/recovery, permissions, secret redaction, memory migration/lifecycle, provider routing/timeouts, browser prompt-injection isolation, file/path security, computer-use confidence, diagnostics truthfulness, backup/restore integrity, self-development boundaries, release/rollback gates and packaging/version metadata.

## Packaging changes

When packaging/build/installer code changes, the exact resulting commit must pass Windows regression, frozen EXE build, PE metadata verification, package secret exclusion, installer build, isolated install/uninstall and post-packaging regression. Do not reuse artifacts/evidence from an older commit.

## Documentation

Update documentation when behavior, configuration, security boundaries or release steps change. Historical V7/V7.5 filenames may remain for link compatibility, but their content must not become an independent product-version authority.

## Pull requests

A good PR states what changed, why, how it was tested, security/permission impact, how success is verified, known limitations and the rollback/revert path for non-trivial changes.

## Bug reports

Include branch/commit, Windows/Python version, reproduction steps, expected vs actual behavior, safe/redacted logs/screenshots and relevant self-check output. Never include secrets.

## Style

Prefer straightforward Python, explicit error handling, bounded retries, explicit composition/dependency injection and clear data contracts over hidden global mutation.

## License

By contributing, you agree that your contribution may be distributed under the repository's MIT License.
