param(
    [switch]$Clean = $true
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$Version = (& $Python -c "from jarvis.version import APP_VERSION; print(APP_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $Version) { throw 'Could not read canonical application version.' }

$ProductBinaryName = 'JARVIS-OMEGA'
Write-Host "JARVIS AI OMEGA $Version // Windows Build" -ForegroundColor Cyan
Write-Host "Python: $Python"

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Install it deliberately with: .\.venv\Scripts\python.exe -m pip install pyinstaller'
}

& $Python -c "import edge_tts, pyttsx3, pyautogui, sounddevice, speech_recognition"
if ($LASTEXITCODE -ne 0) {
    throw 'A required Windows voice/microphone/desktop dependency is unavailable. Install requirements.txt, requirements-windows.txt, and requirements-build.txt.'
}

& $Python -m compileall -f -q .
if ($LASTEXITCODE -ne 0) { throw 'compileall failed; build stopped.' }

& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; build stopped.' }

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $Root 'build') -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Root "dist\$ProductBinaryName") -ErrorAction SilentlyContinue
    # Remove the historical V7-named output so stale binaries cannot be mistaken
    # for the current release candidate after a successful rebuild.
    Remove-Item -Recurse -Force (Join-Path $Root 'dist\JARVIS-OMEGA-V7') -ErrorAction SilentlyContinue
}

$Args = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--windowed',
    '--name', $ProductBinaryName,
    '--collect-submodules', 'jarvis',
    '--collect-submodules', 'edge_tts',
    '--collect-submodules', 'speech_recognition',
    '--collect-all', 'sounddevice',
    '--collect-submodules', 'pyautogui',
    'desktop_app.py'
)
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Dist = Join-Path $Root "dist\$ProductBinaryName"
$Exe = Join-Path $Dist "$ProductBinaryName.exe"
if (-not (Test-Path $Exe)) { throw "Expected executable was not created: $Exe" }

# Prove the frozen executable contains the TTS worker and can spawn that worker
# without entering first-run/bootstrap or opening a duplicate desktop GUI. This is
# deliberately non-audio: real speaker output remains a real-machine release gate.
& $Exe --tts-runtime-healthcheck
if ($LASTEXITCODE -ne 0) { throw 'Packaged TTS runtime healthcheck failed.' }

# Public documentation/config template only. Never copy the operator's .env,
# Google OAuth files, tokens, database, logs or other private runtime data.
Copy-Item (Join-Path $Root '.env.example') (Join-Path $Dist '.env.example') -Force
Copy-Item (Join-Path $Root 'README.md') (Join-Path $Dist 'README.md') -Force
Copy-Item (Join-Path $Root 'LICENSE') (Join-Path $Dist 'LICENSE') -Force

& $Python (Join-Path $Root 'scripts\validate_release_bundle.py') $Dist
if ($LASTEXITCODE -ne 0) { throw 'Release bundle secret/private-data validation failed.' }

Write-Host "Build ready: $Exe" -ForegroundColor Green
Write-Host "Version: $Version" -ForegroundColor Green
Write-Host 'Private .env / OAuth / database files were NOT bundled.' -ForegroundColor Yellow
