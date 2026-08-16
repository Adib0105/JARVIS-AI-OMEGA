$ErrorActionPreference = "Stop"
Write-Host "=== JARVIS OMEGA V6 - Installer Build ===" -ForegroundColor Cyan

if (-not (Test-Path ".\dist\JARVIS-OMEGA-V6\JARVIS-OMEGA-V6.exe")) {
    throw "Desktop EXE build not found. Run .\build_windows.ps1 first."
}

$candidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install it, then run this script again."
}

& $iscc ".\installer\JARVIS-OMEGA-V6.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed." }

Write-Host "Installer ready under .\dist\installer" -ForegroundColor Green
