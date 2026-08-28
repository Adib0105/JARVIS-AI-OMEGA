# Release Process

Release authority comes from `jarvis.version.APP_VERSION`. The executable name remains stable as `JARVIS-OMEGA.exe`; the installer filename carries the version.

A releasable commit requires:

1. clean reviewed branch/PR state;
2. compile and full regression pass;
3. critical Ruff, high Bandit, dependency and secret-exclusion gates;
4. Windows EXE build with canonical version resources;
5. package/first-run/TTS-worker software healthchecks;
6. Inno installer build and SHA-256 manifest;
7. isolated install, repair/upgrade, uninstall and data-preservation checks;
8. post-package regression;
9. exact-candidate workstation/live-provider evidence before a final production-ready claim.

The CI workflow implements the automated chain. It does not provide branch protection, commit/tag signing, Authenticode signing or physical-device proof. See `docs/V7-RELEASE.md`, `docs/BASELINE-REPORT.md` and `docs/WINDOWS-E2E-CHECKLIST.md`.

