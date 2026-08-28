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
if ($LASTEXITCODE -ne 0 -or -not $WindowsVersion) { throw 'Could not derive canonical Windows file version.' }

$ProductBinaryName = 'JARVIS-OMEGA'
$Iss = Join-Path $Root 'installer\JarvisOmega.iss'
$BuiltExe = Join-Path $Root "dist\$ProductBinaryName\$ProductBinaryName.exe"
if (-not (Test-Path $BuiltExe)) {
    throw "Executable is missing: $BuiltExe. Run .\build_windows.ps1 first."
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

& $Iscc "/DMyAppVersion=$Version" "/DMyWindowsVersion=$WindowsVersion" $Iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }

$Installer = Join-Path $Root "dist\installer\JARVIS-AI-OMEGA-Setup-$Version.exe"
if (-not (Test-Path $Installer)) { throw "Expected installer was not created: $Installer" }
$Hash = Get-FileHash $Installer -Algorithm SHA256
$InstallerName = Split-Path -Leaf $Installer
$ChecksumLine = "$($Hash.Hash.ToLowerInvariant())  $InstallerName"
$ChecksumLine | Set-Content (Join-Path $Root 'dist\installer\SHA256.txt') -Encoding ascii
Write-Host "Installer ready: $Installer" -ForegroundColor Green
Write-Host "Version: $Version ($WindowsVersion)" -ForegroundColor Green
Write-Host "SHA-256: $($Hash.Hash)" -ForegroundColor Green
