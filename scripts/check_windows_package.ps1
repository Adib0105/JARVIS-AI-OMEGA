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
# Validate optional native imports and the bundled Playwright driver, without recording.
$backgroundCheck = Start-Process -FilePath $exe -ArgumentList @('--jarvis-background-check') -PassThru
if (-not $backgroundCheck.WaitForExit(30000)) {
  $backgroundCheck.Kill()
  throw 'Frozen background dependency check did not exit within 30 seconds.'
}
if ($backgroundCheck.ExitCode -ne 0) { throw 'Frozen background dependency check failed.' }
Write-Host "Package smoke PASS: $exe"
# Launch a complete fresh desktop from a directory containing spaces, without any key.
$SmokeRoot = Join-Path $env:RUNNER_TEMP 'JARVIS fresh install'
if (-not $env:RUNNER_TEMP) { $SmokeRoot = Join-Path $env:TEMP ('JARVIS fresh ' + [guid]::NewGuid()) }
New-Item -ItemType Directory -Path $SmokeRoot -Force | Out-Null
Copy-Item "$dist\*" $SmokeRoot -Recurse -Force
$Report = Join-Path (Get-Location) 'desktop-smoke.json'
Remove-Item -LiteralPath $Report -ErrorAction SilentlyContinue
$env:AI_PROVIDER = 'openrouter'
$env:OPENROUTER_API_KEY = ''
$env:OPENAI_API_KEY = ''
$env:ENABLE_MIC_INPUT = 'false'
$env:ENABLE_WAKE_WORD = 'false'
$env:ENABLE_LIVE_CONVERSATION = 'false'
$env:ENABLE_VOICE_OUTPUT = 'false'
$FreshExe = Join-Path $SmokeRoot 'JARVIS-OMEGA-V7.exe'
$desktop = Start-Process -FilePath $FreshExe -WorkingDirectory $env:TEMP -ArgumentList @('--jarvis-desktop-smoke', ('"' + $Report + '"')) -PassThru
if (-not $desktop.WaitForExit(60000)) {
  $desktop.Kill()
  throw 'Fresh desktop launch hung or failed to close.'
}
if ($desktop.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw 'Fresh desktop launch failed; inspect desktop-smoke.json.' }
$Result = Get-Content $Report -Raw | ConvertFrom-Json
if (-not $Result.ok) { throw 'Fresh desktop reported a startup or Tk rendering error.' }
Write-Host 'Full desktop launch, avatar rendering and shutdown PASS without API credentials.'
