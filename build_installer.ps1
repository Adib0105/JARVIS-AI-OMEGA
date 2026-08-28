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
$InstallerName = (& $Python -c "from jarvis.version import WINDOWS_INSTALLER_BASENAME; print(WINDOWS_INSTALLER_BASENAME)").Trim()
if (-not $Version -or -not $ProductName -or -not $ArtifactName -or -not $InstallerName) {
    throw 'Unable to load canonical version metadata from jarvis/version.py.'
}

$Iss = Join-Path $Root 'installer\JARVIS-OMEGA-V7.5.iss'
$BuiltExe = Join-Path $Root "dist\$ArtifactName\$ArtifactName.exe"
if (-not (Test-Path $BuiltExe)) {
    throw "$ArtifactName executable is missing. Run .\build_windows.ps1 first."
}

$Candidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$Iscc = $Candidates | Select-Object -First 1
if (-not $Iscc) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $Iscc = $cmd.Source }
}
if (-not $Iscc) {
    throw 'Inno Setup 6 compiler (ISCC.exe) was not found. Install it deliberately, then rerun this script.'
}

$Defines = @(
    "/DMyAppVersion=$Version",
    "/DMyAppName=$ProductName",
    "/DMyAppExeName=$ArtifactName.exe",
    "/DMyArtifactName=$ArtifactName",
    "/DMyInstallerBase=$InstallerName"
)
& $Iscc @Defines $Iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }

$Installer = Join-Path $Root "dist\installer\$InstallerName.exe"
if (-not (Test-Path $Installer)) { throw "Expected installer was not created: $Installer" }
Write-Host "Installer ready: $Installer" -ForegroundColor Green
