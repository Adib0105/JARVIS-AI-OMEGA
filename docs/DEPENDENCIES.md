# Reproducing the JARVIS AI OMEGA 8.0.0-rc1 Release Environment

The release path uses exact direct dependency pins plus `constraints-release.txt` for transitive resolution. The constraints were captured from a successful Windows Python 3.14.7 package build, then must be re-validated by the full CI matrix on every commit that changes them.

## Supported Python compatibility gate

Automated regression targets Linux Python 3.11, 3.12, 3.13 and 3.14. The Windows release candidate build is anchored to Python 3.14.7.

## Windows release environment

Create a clean virtual environment and install exactly the constrained runtime, Windows and build dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.2.1
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt
```

The CI installer job uses Inno Setup 6.7.1. `build_installer.ps1` reads the application and Windows numeric version from `jarvis.version`; callers must not pass a separate release version.

## Change policy

Do not upgrade dependency pins merely because a newer package exists. For a dependency change:

1. state the compatibility/security reason;
2. change the smallest required set of pins/constraints;
3. run compile checks and focused tests;
4. run the full Linux 3.11–3.14 and Windows 3.14.7 regression matrix;
5. rebuild the frozen EXE and installer;
6. run isolated installer validation and post-packaging regression;
7. retain the exact workflow run as evidence for that commit.

If a pin is incompatible with any supported Python version, CI must fail; do not relax or skip that platform merely to make the release green.

## Limits of reproducibility

Exact Python package resolution is controlled by the checked-in requirement/constraint files. Hosted CI runner images, operating-system updates, certificates, network availability and package-index availability are external inputs and can still change. A truly archival release should additionally retain the generated installer checksum and, where long-term offline reproducibility is required, a vetted wheelhouse/artifact set for the supported platform.
