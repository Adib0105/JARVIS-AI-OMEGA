param(
    [string]$Version = '8.0.0-rc1',
    [string]$WindowsVersion = '8.0.0.1'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Iss = Join-Path $Root 'installer\JarvisOmega.iss'
$BuiltExe = Join-Path $Root 'dist\JARVIS-OMEGA-V7\JARVIS-OMEGA-V7.exe'
if (-not (Test-Path $BuiltExe)) {
    throw 'V7 executable is missing. Run .\build_windows.ps1 first.'
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
$Hash.Hash | Set-Content (Join-Path $Root 'dist\installer\SHA256.txt')
Write-Host "Installer ready: $Installer" -ForegroundColor Green
Write-Host "SHA-256: $($Hash.Hash)" -ForegroundColor Green
