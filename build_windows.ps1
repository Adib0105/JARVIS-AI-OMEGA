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

Write-Host 'JARVIS AI OMEGA V7 // Windows Build' -ForegroundColor Cyan
Write-Host "Python: $Python"

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Install it deliberately with: .\.venv\Scripts\python.exe -m pip install pyinstaller'
}

& $Python -m compileall -f -q jarvis tests desktop_app.py main.py self_check.py self_check_v75.py
if ($LASTEXITCODE -ne 0) { throw 'compileall failed; build stopped.' }

& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; build stopped.' }

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $Root 'build') -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Root 'dist\JARVIS-OMEGA-V7') -ErrorAction SilentlyContinue
}

$Args = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--windowed',
    '--name', 'JARVIS-OMEGA-V7',
    '--collect-submodules', 'jarvis',
    '--collect-submodules', 'edge_tts',
    '--collect-submodules', 'pyttsx3.drivers',
    '--collect-submodules', 'speech_recognition',
    '--hidden-import', 'pystray._win32',
    '--collect-all', 'playwright',
    'desktop_app.py'
)
# Include optional offline recognition only when deliberately installed in the build environment.
& $Python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('vosk') else 1)"
if ($LASTEXITCODE -eq 0) {
    $Args = $Args[0..($Args.Length - 2)] + @('--collect-all', 'vosk', 'desktop_app.py')
}
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Dist = Join-Path $Root 'dist\JARVIS-OMEGA-V7'
$Exe = Join-Path $Dist 'JARVIS-OMEGA-V7.exe'
if (-not (Test-Path $Exe)) { throw "Expected executable was not created: $Exe" }

# Public documentation/config template only. Never copy the operator's .env,
# Google OAuth files, tokens, database, logs or other private runtime data.
Copy-Item (Join-Path $Root '.env.example') (Join-Path $Dist '.env.example') -Force
Copy-Item (Join-Path $Root 'README.md') (Join-Path $Dist 'README.md') -Force
Copy-Item (Join-Path $Root 'setup_background_startup.ps1') (Join-Path $Dist 'setup_background_startup.ps1') -Force
Copy-Item (Join-Path $Root 'docs\BACKGROUND-WAKE.md') (Join-Path $Dist 'BACKGROUND-WAKE.md') -Force
Copy-Item (Join-Path $Root 'LICENSE') (Join-Path $Dist 'LICENSE') -Force

Write-Host "Build ready: $Exe" -ForegroundColor Green
Write-Host 'Private .env / OAuth / database files were NOT bundled.' -ForegroundColor Yellow
