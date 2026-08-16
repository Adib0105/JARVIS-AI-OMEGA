# Contributing to JARVIS AI OMEGA

Thanks for helping improve JARVIS AI OMEGA.

The project values **reliability, verification, safety, clear evidence and focused changes** over feature count.

## Branch strategy

- `main` — stable V6 baseline until the final V7 release decision
- `v7-development` — active V7/V7.5 engineering

New V7/V7.5 work should target `v7-development` unless a maintainer explicitly asks for something else.

## Before you start

1. Search existing issues and documentation.
2. Read [README.md](README.md), [SECURITY.md](SECURITY.md) and [docs/README.md](docs/README.md).
3. For architecture-sensitive work, also read the relevant V7 document.
4. Keep the change narrow enough to test and review.

## Development setup

Windows setup:

```powershell
git fetch origin
git switch v7-development
git pull origin v7-development
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

See [docs/V7-SETUP.md](docs/V7-SETUP.md) for the full setup guide.

## Quality gate

Before opening a pull request:

```powershell
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

When useful, also run:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe self_check_v75.py
```

Do not delete, skip or weaken a regression test only to make CI green. Fix the root cause or explain the limitation.

## Engineering rules

A feature is not complete simply because code exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

For real-world actions, a successful tool return is not automatically proof that the requested effect happened. Add observable verification whenever practical.

## Security rules

Never commit:

- `.env`
- API keys
- passwords
- OAuth secrets/tokens
- recovery codes
- SSH/private keys
- private databases or credential exports

New tools must be narrow, capability-profiled, auditable and permission-aware.

Do not add:

- unrestricted arbitrary shell execution
- credential scraping
- hidden persistence or stealth behavior
- permission/audit bypasses
- self-development paths that can rewrite protected security/rollback/secret controls

Web/search/page content must remain untrusted data.

## Computer-use changes

Computer-use changes should preserve the V7 reliability model:

```text
semantic target → confidence/ambiguity gate → action → observation → verification
```

Low-confidence targets should stop safely rather than guess. Do not use coordinate clicking as the default targeting strategy.

## Self-development changes

Controlled self-development must remain sandbox-first:

```text
Gap → Proposal → Isolated Worktree → Build → Tests → Security/Evaluation
→ Diff → Approval → Controlled Release
```

`APPROVED` must not silently become `DEPLOYED`.

Protected security, secret, sandbox and rollback boundaries are not normal self-modification targets.

## Tests

Add or update deterministic tests when behavior changes. Prefer tests that prove externally observable contracts rather than implementation trivia.

Important test areas include:

- mission verification/recovery
- permission/security behavior
- secret redaction
- memory migration/lifecycle
- browser prompt-injection isolation
- computer-use confidence behavior
- backup/restore integrity
- self-development sandbox boundaries
- release/rollback gates

## Documentation

Update documentation when behavior, configuration, security boundaries or release steps change.

Common files:

- `README.md`
- `CHANGELOG.md`
- `docs/V7.5-STATUS.md`
- `ROADMAP.md`
- subsystem-specific docs under `docs/`

## Pull requests

Use the repository PR template. A good PR should explain:

- what changed
- why it changed
- how it was tested
- security/permission impact
- how success is verified
- rollback/revert path for non-trivial changes

Keep unrelated refactors out of focused fixes when possible.

## Bug reports

Use the GitHub bug template and include:

- branch/commit
- Windows/Python version
- exact reproduction steps
- expected behavior
- actual behavior
- safe/redacted logs or screenshots
- relevant self-check output

Never include secrets in issues.

## Style

Prefer straightforward Python, explicit error handling, bounded retries and clear data contracts. Avoid hidden global behavior when dependency injection or explicit configuration is practical.

## License

By contributing, you agree that your contribution may be distributed under the repository's MIT License.
