# JARVIS AI OMEGA — Testing & Evaluation

The filename is historical. Current release/version claims derive from `jarvis.version.APP_VERSION`.

## Quality rule

A module existing or importing successfully is not proof that the feature works end to end.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Runtime diagnostics distinguish `INSTALLED`, `CONFIGURED`, `LOCAL_FUNCTIONAL`, `INTEGRATION_TESTED`, `DEVICE_VERIFIED`, `E2E_VERIFIED`, `DEGRADED`, `FAILED` and `NOT_TESTED`.

## Local developer gate

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe self_check.py
.\.venv\Scripts\python.exe -m compileall -f -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`self_check_v75.py` is retained only as a backward-compatible wrapper.

Run the full suite after touching shared runtime, security, memory, provider routing, computer-use, packaging, self-development or storage code.

## CI matrix

Automated regression covers:

- Linux Python 3.11;
- Linux Python 3.12;
- Linux Python 3.13;
- Linux Python 3.14;
- Windows Python 3.14.7.

CI uses pip 26.2.1 plus `constraints-release.txt` and exact direct dependency pins. `ResourceWarning` is promoted to an error so leaked file/database handles cannot be ignored.

## Windows packaging gate

After Windows regression passes, CI builds the frozen application and installer.

Automated packaging evidence includes:

- `dist/JARVIS-OMEGA/JARVIS-OMEGA.exe` produced;
- canonical Windows PE file/product version metadata embedded and verified;
- first-run/package/TTS-worker software healthchecks;
- `.env`, live databases, OAuth credentials/tokens and other private material excluded;
- installer generated from canonical application version;
- installer SHA-256 generated;
- isolated installation without repository checkout or Python setup;
- installed-app healthchecks;
- shortcuts and uninstaller present;
- uninstall preserves per-user data;
- full post-packaging regression.

This does not prove physical speaker/microphone behavior, live provider responses or real desktop UI effects.

## Test categories

The repository contains deterministic coverage for provider contracts/routing/timeouts/fallbacks; mission persistence, verification, recovery and replanning; capability permissions and Trusted Local Mode boundaries; secret detection/redaction; memory/RAG/document lifecycle; Computer Use confidence/ambiguity/OCR behavior; browser trust and prompt-injection isolation; controlled self-development and rollback; skill lifecycle controls; backup/integrity; observability; diagnostics truthfulness; canonical versioning; file-root/symlink/junction security; and Windows release-script consistency.

## Evaluation benchmark

`jarvis/evaluation/benchmark.py` stores deterministic scenario results. Supported categories include task success, tool accuracy, verification accuracy, recovery, replanning, safety, memory accuracy, computer-use accuracy, browser accuracy and average latency.

A model statement that performance improved is not benchmark evidence. Before/after claims must bind to actual measured runs.

## Adversarial security expectations

Tests should fail safely for prompt injection, secret extraction/persistence, private browser targets, unknown tools, permission bypass, path/sandbox escape, security-core self-modification, unrestricted shell exposure and Trusted Local Mode high-risk bypass.

Security failures block release readiness.

## Exact-commit evidence rule

Never reuse CI, package, device or live-provider evidence from an older commit after source/dependency/build changes. The exact commit being released must have its own qualifying evidence.

## Real Windows workstation gate

CI cannot prove every real-device behavior. Use [WINDOWS-E2E-CHECKLIST.md](WINDOWS-E2E-CHECKLIST.md) for the exact release candidate and record untested areas as `NOT VERIFIED`.

Important real-machine checks include GUI startup/shutdown, Chrome/Notepad control, UIA and OCR behavior, focus handling, keyboard/mouse effects plus post-action verification, DPI/resolution movement, audible TTS, microphone/speech recognition, real provider inference and failure behavior, network disconnect/reconnect, and clean installed first run/uninstall.

## Debugging red CI

1. Identify the first meaningful failure.
2. Reproduce on the closest local platform when possible.
3. Fix the violated contract/root cause.
4. Run focused tests.
5. Run the full suite.
6. Rebuild/repackage when packaging code changed.
7. Accept release evidence only for the resulting exact commit.

Do not add arbitrary sleeps, skips, weakened assertions or hard-coded PASS states merely to make CI green.

## Release rule

A green automated workflow is required but not sufficient. Do not claim hardware, live-provider or real UI behavior as verified unless it was actually tested for the exact candidate.
