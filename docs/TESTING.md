# Hardening verification

From a clean environment with `requirements.txt` installed:

```sh
python -m pip check
python -m compileall -f -q jarvis tests main.py
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p test_final_hardening.py -v
python -m unittest discover -s tests -p test_v7_security.py -v
```

Use `PYTHONWARNINGS=error::ResourceWarning` for regression runs. CI enforces this on Linux and Windows. Dedicated adversarial tests are also a separate mandatory step in both regression jobs.

The 2026-09-21 Linux run passed 369 tests, including 23 dedicated final-hardening adversarial tests and 13 V7 permission/security tests. See [the audit](FINAL-HARDENING-AUDIT.md) for baseline-failure evidence and limitations. Counts overlap; do not add them.

Attack-category tests prove execution is denied before subprocess creation. They do not prove an operational OS sandbox. Self-development lifecycle tests use a reviewed, test-only hello fixture runner to preserve their original workflow assertions; that runner is never selected by production code.

Windows validation must use the existing Windows CI jobs and retained launch/installer/Defender artifacts. A complete release review additionally needs real first-run voice/AI/browser/shutdown checks, audio device failure recovery and broken-update rollback. These have not been run on this Linux host. Passing ordinary updater mocks is not rollback proof.

Do not re-enable publication based only on a green unit suite. Resolve the audit matrix, provide required Windows evidence, configure protected required checks, and review the release gate before publishing.
