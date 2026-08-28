# Testing

Canonical local software checks:

```powershell
python -m compileall -f -q .
python -m unittest discover -s tests -v
ruff check . --select E9,F63,F7,F82
bandit -q -r jarvis scripts desktop_app.py main.py self_check.py self_check_release.py -lll
pip check
pip-audit -r requirements.txt
```

The 2026-08-28 hardening run passed 432 tests on Linux/Python 3.12.13 with one expected Windows-junction skip. Automated tests cover mission/security/result semantics, browser/file boundaries, memory, recovery, observability, accounts, updater, packaging contracts, voice logic and Windows-control contracts.

Automated software checks do not prove physical microphone capture, audible TTS, real UIA/OCR interaction, live provider behavior or human installer UX. Use `docs/WINDOWS-E2E-CHECKLIST.md` for exact-candidate evidence. See `docs/BASELINE-REPORT.md` and `docs/V7-TESTING.md` for results and detailed scope.
