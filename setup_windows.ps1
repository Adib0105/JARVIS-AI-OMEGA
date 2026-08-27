param(
    [switch]$IncludeBuildTools
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host '=== JARVIS AI OMEGA // Windows Setup ===' -ForegroundColor Cyan

$pythonCommand = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py).Source
} else {
    throw 'Python 3.11+ not found. Install Python and enable it on PATH.'
}

if (-not (Test-Path '.venv')) {
    Write-Host 'Creating isolated environment...' -ForegroundColor Cyan
    & $pythonCommand -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}

$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) { throw "Virtual-environment Python is missing: $venvPython" }

& $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw 'JARVIS AI OMEGA requires Python 3.11 or newer.' }

$PythonVersion = (& $venvPython -c "import platform; print(platform.python_version())").Trim()
$Version = (& $venvPython -c "from jarvis.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $Version) { throw 'Could not read canonical application version.' }

Write-Host "JARVIS AI OMEGA $Version" -ForegroundColor Cyan
Write-Host "Python: $PythonVersion"
if ($PythonVersion -ne '3.14.7') {
    Write-Warning "Python $PythonVersion is supported for source use when tests pass, but the exact Windows release-build baseline is Python 3.14.7."
}

Write-Host 'Installing pinned pip baseline...' -ForegroundColor Cyan
& $venvPython -m pip install pip==26.2.1
if ($LASTEXITCODE -ne 0) { throw 'Pinned pip installation failed.' }

Write-Host 'Installing constrained runtime dependencies...' -ForegroundColor Cyan
& $venvPython -m pip install -c constraints-release.txt -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Core dependency installation failed.' }

Write-Host 'Installing constrained Windows desktop/voice dependencies...' -ForegroundColor Cyan
& $venvPython -m pip install -c constraints-release.txt -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) {
    throw 'Windows desktop/voice dependency installation failed. The Windows setup is incomplete.'
}

if ($IncludeBuildTools) {
    Write-Host 'Installing constrained release build dependencies...' -ForegroundColor Cyan
    & $venvPython -m pip install -c constraints-release.txt -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Release build dependency installation failed.' }
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env from .env.example. Add local provider credentials there; never commit them.' -ForegroundColor Green
} else {
    Write-Host 'Existing .env kept unchanged.' -ForegroundColor Yellow
}

Write-Host 'Running canonical release self-check...' -ForegroundColor Cyan
& $venvPython self_check.py
if ($LASTEXITCODE -ne 0) {
    throw 'Canonical self-check reported a failure. Review the diagnostic states above before launching.'
}

Write-Host ''
Write-Host "Setup complete for JARVIS AI OMEGA $Version." -ForegroundColor Green
Write-Host '1. Configure provider/API credentials in .env.' -ForegroundColor White
Write-Host '2. Re-run diagnostics: .\.venv\Scripts\python.exe self_check.py'
Write-Host '3. Launch desktop: .\run_desktop.bat'
Write-Host '4. Launch terminal: .\run_jarvis.bat'
if (-not $IncludeBuildTools) {
    Write-Host '5. For packaging tools, re-run: .\setup_windows.ps1 -IncludeBuildTools'
}
Write-Host ''
Write-Host 'Physical microphone, audible TTS, real desktop actions and live provider inference remain separate device/E2E verification gates.' -ForegroundColor Yellow
