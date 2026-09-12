$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$dist = '.\dist\JARVIS-OMEGA-V7'
$exe = Join-Path $dist 'JARVIS-OMEGA-V7.exe'
if (-not (Test-Path $exe)) { throw "Packaged EXE missing: $exe" }
$forbidden = Get-ChildItem $dist -Recurse -File | Where-Object {
  $_.Name -eq '.env' -or
  $_.Extension -in @('.db', '.sqlite', '.sqlite3') -or
  $_.Name -in @('google_token.json', 'google_credentials.json')
}
if ($forbidden) {
  $forbidden | ForEach-Object { Write-Host "FORBIDDEN BUNDLE FILE: $($_.FullName)" }
  throw 'Secrets/private runtime data must not be bundled.'
}
# A frozen speech child must dispatch without opening a second GUI.
$worker = Start-Process -FilePath $exe -ArgumentList @('--jarvis-speech-worker', '--help') -PassThru
if (-not $worker.WaitForExit(30000)) {
  $worker.Kill()
  throw 'Frozen speech worker did not exit within 30 seconds.'
}
if ($worker.ExitCode -ne 0) { throw 'Frozen speech worker startup failed.' }
Write-Host "Package smoke PASS: $exe"
