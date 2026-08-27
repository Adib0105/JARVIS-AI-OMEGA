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
$WindowsVersion = (& $Python -c "from jarvis.version import WINDOWS_FILE_VERSION; print(WINDOWS_FILE_VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $WindowsVersion) { throw 'Could not read canonical Windows file version.' }

$ProductBinaryName = 'JARVIS-OMEGA'
Write-Host "JARVIS AI OMEGA $Version // Windows Build" -ForegroundColor Cyan
Write-Host "Python: $Python"
Write-Host "Windows file version: $WindowsVersion"

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Install it deliberately with: .\.venv\Scripts\python.exe -m pip install -c constraints-release.txt -r requirements-build.txt'
}

& $Python -c "import edge_tts, pyttsx3, pyautogui, pywinauto, sounddevice, speech_recognition"
if ($LASTEXITCODE -ne 0) {
    throw 'A required Windows voice/microphone/desktop dependency is unavailable. Install the constrained runtime and Windows requirement sets.'
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

$VersionInfo = Join-Path $Root 'build\release-metadata\JARVIS-OMEGA-version.txt'
& $Python (Join-Path $Root 'scripts\generate_windows_version_info.py') $VersionInfo
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VersionInfo)) {
    throw 'Could not generate canonical Windows EXE version metadata.'
}

$Args = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--windowed',
    '--name', $ProductBinaryName,
    '--version-file', $VersionInfo,
    '--collect-submodules', 'jarvis',
    '--collect-submodules', 'edge_tts',
    '--collect-submodules', 'speech_recognition',
    '--collect-submodules', 'pywinauto',
    '--collect-all', 'sounddevice',
    '--collect-submodules', 'pyautogui',
    'desktop_app.py'
)
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Dist = Join-Path $Root "dist\$ProductBinaryName"
$Exe = Join-Path $Dist "$ProductBinaryName.exe"
if (-not (Test-Path $Exe)) { throw "Expected executable was not created: $Exe" }

# Validate the actual frozen PE resource rather than trusting the build arguments.
$VersionInfoActual = (Get-Item $Exe).VersionInfo
$ActualFileVersion = [string]$VersionInfoActual.FileVersion
$ActualProductVersion = [string]$VersionInfoActual.ProductVersion
if ($ActualFileVersion -ne $WindowsVersion) {
    throw "Frozen EXE file version mismatch. Expected $WindowsVersion, got $ActualFileVersion"
}
if ($ActualProductVersion -ne $Version) {
    throw "Frozen EXE product version mismatch. Expected $Version, got $ActualProductVersion"
}
Write-Host "Verified EXE metadata: FileVersion=$ActualFileVersion ProductVersion=$ActualProductVersion" -ForegroundColor Green

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