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
$ProductName = (& $Python -c "from jarvis.version import PRODUCT_DISPLAY_NAME; print(PRODUCT_DISPLAY_NAME)").Trim()
$ArtifactName = (& $Python -c "from jarvis.version import WINDOWS_ARTIFACT_BASENAME; print(WINDOWS_ARTIFACT_BASENAME)").Trim()
if (-not $Version -or -not $ProductName -or -not $ArtifactName) {
    throw 'Unable to load canonical version metadata from jarvis/version.py.'
}

Write-Host "$ProductName $Version // Windows Build" -ForegroundColor Cyan
Write-Host "Python: $Python"

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Install it deliberately with: .\.venv\Scripts\python.exe -m pip install pyinstaller'
}

& $Python -m compileall -f -q .
if ($LASTEXITCODE -ne 0) { throw 'compileall failed; build stopped.' }

& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; build stopped.' }

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $Root 'build') -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Root "dist\$ArtifactName") -ErrorAction SilentlyContinue
}

$Args = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--windowed',
    '--name', $ArtifactName,
    '--collect-submodules', 'jarvis',
    '--collect-submodules', 'edge_tts',
    '--collect-submodules', 'speech_recognition',
    'desktop_app.py'
)
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Dist = Join-Path $Root "dist\$ArtifactName"
$Exe = Join-Path $Dist "$ArtifactName.exe"
if (-not (Test-Path $Exe)) { throw "Expected executable was not created: $Exe" }

# Public documentation/config template only. Never copy the operator's .env,
# Google OAuth files, tokens, database, logs or other private runtime data.
Copy-Item (Join-Path $Root '.env.example') (Join-Path $Dist '.env.example') -Force
Copy-Item (Join-Path $Root 'README.md') (Join-Path $Dist 'README.md') -Force
Copy-Item (Join-Path $Root 'LICENSE') (Join-Path $Dist 'LICENSE') -Force

Write-Host "Build ready: $Exe" -ForegroundColor Green
Write-Host 'Private .env / OAuth / database files were NOT bundled.' -ForegroundColor Yellow
