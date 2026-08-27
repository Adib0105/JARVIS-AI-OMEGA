# Reproducing the JARVIS AI OMEGA 8.0.0-rc1 Release Environment

The release path uses exact direct dependency pins plus `constraints-release.txt` for transitive resolution. The constraints were captured from a successful Windows Python 3.14.7 package build and must be re-validated by the full CI matrix on every commit that changes dependencies or release tooling.

## Supported Python compatibility gate

Automated regression targets Linux Python 3.11, 3.12, 3.13 and 3.14. The exact Windows release build is anchored to Python 3.14.7.

## Canonical Windows setup

For normal Windows source use:

```powershell
.\setup_windows.ps1
```

The setup script creates/uses `.venv`, pins pip to 26.2.1, installs runtime and Windows dependencies through `constraints-release.txt`, preserves existing local `.env` configuration and runs the canonical self-check.

For release-build tooling too:

```powershell
.\setup_windows.ps1 -IncludeBuildTools
```

## Exact release environment

Equivalent explicit commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.2.1
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt
```

The CI installer job uses Inno Setup 6.7.1.

## Versioned release metadata

`jarvis.version.APP_VERSION` is the single application release authority. `WINDOWS_FILE_VERSION` is derived from it.

- `build_windows.ps1` generates a PyInstaller Windows PE version-resource file from those canonical values, embeds it in `JARVIS-OMEGA.exe`, then verifies the actual built executable metadata.
- `build_installer.ps1` reads the same canonical application/Windows versions and passes them to `installer/JarvisOmega.iss`.

Callers must not pass or hard-code a separate application release version.

## Change policy

Do not upgrade pins merely because newer packages exist. For a dependency/build-tool change:

1. state the compatibility/security reason;
2. change the smallest required pin/constraint set;
3. run compile checks and focused tests;
4. run the full Linux 3.11–3.14 and Windows 3.14.7 regression matrix;
5. rebuild the frozen EXE and verify its PE metadata;
6. rebuild the installer;
7. run isolated installer validation and post-packaging regression;
8. retain evidence only for the exact resulting commit.

If a pin is incompatible with a supported Python version, CI must fail. Do not relax or skip that platform merely to make the release green.

## Limits of reproducibility

Exact Python package resolution is controlled by the checked-in requirement/constraint files, but hosted runner images, operating-system updates, certificates, network availability, package-index availability and external installer repositories remain external inputs.

For long-term archival/offline reproduction, additionally retain a vetted wheelhouse/build-tool artifact set plus the generated installer and checksum for the exact release.
