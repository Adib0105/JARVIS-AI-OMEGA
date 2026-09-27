$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$Installer = (Resolve-Path '.\dist\installer\JARVIS-AI-OMEGA-V7-Setup.exe').Path
$InstallDir = Join-Path $env:RUNNER_TEMP 'JARVIS installed test'
$Args = @('/SP-', '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES', ('/DIR="' + $InstallDir + '"'))
$p = Start-Process $Installer -ArgumentList $Args -PassThru -Wait
if ($p.ExitCode -ne 0) { throw 'Fresh installer failed.' }
$Shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'JARVIS AI OMEGA V7.lnk'
if (-not (Test-Path -LiteralPath $Shortcut)) { throw 'Desktop shortcut not created.' }
$Link = (New-Object -ComObject WScript.Shell).CreateShortcut($Shortcut)
$InstalledExe = Join-Path $InstallDir 'JARVIS-OMEGA-V7.exe'
if ($Link.TargetPath -ne $InstalledExe) { throw 'Desktop shortcut targets the wrong executable.' }
# Exercise the same updater helper users run, with synthetic data only.
$SavedEnv = "# settings preservation sentinel`nAI_PROVIDER=openrouter`nOPENROUTER_API_KEY=`nENABLE_MIC_INPUT=false`nENABLE_VOICE_OUTPUT=false`n"
$EnvFile = Join-Path $InstallDir '.env'
[IO.File]::WriteAllText($EnvFile, $SavedEnv)
New-Item -ItemType Directory (Join-Path $InstallDir 'data') -Force | Out-Null
$DataFile = Join-Path $InstallDir 'data\upgrade-sentinel.txt'
'keep my data' | Set-Content -LiteralPath $DataFile
$Hash = (Get-FileHash $Installer -Algorithm SHA256).Hash
$PowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
& $PowerShell -NoProfile -NonInteractive -File .\scripts\apply-update.ps1 -Installer $Installer -AppDir $InstallDir -ParentId 0 -Sha256 $Hash -NoRelaunch
Get-Content (Join-Path (Split-Path -Parent $Installer) 'update-result.txt') -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw 'Update helper failed.' }
if ([IO.File]::ReadAllText($EnvFile) -ne $SavedEnv) { throw 'Update changed user environment settings.' }
if ((Get-Content $DataFile -Raw).Trim() -ne 'keep my data') { throw 'Update changed user data.' }
$Report = Join-Path (Get-Location) 'installed-desktop-smoke.json'
$p = Start-Process $InstalledExe -WorkingDirectory $env:TEMP -ArgumentList @('--jarvis-desktop-smoke', ('"' + $Report + '"')) -PassThru
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'Installed desktop hung.' }
if ($p.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw 'Installed desktop failed.' }
if (-not (Get-Content $Report -Raw | ConvertFrom-Json).ok) { throw 'Installed desktop smoke failed.' }
# The desktop smoke intentionally saves a synthetic connection through the UI.
# Preserve that current user state across both following updater operations,
# rather than comparing it with the pre-smoke blank-connection fixture.
$CurrentEnv = [IO.File]::ReadAllText($EnvFile)
$CurrentData = [IO.File]::ReadAllText($DataFile)
# Exercise the normal helper relaunch, not only the -NoRelaunch upgrade path.
$env:ENABLE_MIC_INPUT = 'false'
$env:ENABLE_VOICE_OUTPUT = 'false'
& $PowerShell -NoProfile -NonInteractive -File .\scripts\apply-update.ps1 -Installer $Installer -AppDir $InstallDir -ParentId 0 -Sha256 $Hash
if ($LASTEXITCODE -ne 0) { throw 'Updated desktop did not report readiness.' }
$Ready = Join-Path (Split-Path -Parent $Installer) 'update-result.txt.desktop-ready'
if (-not (Test-Path -LiteralPath $Ready)) { throw 'Updater relaunch readiness file is missing.' }
if (-not (Get-Content -LiteralPath $Ready -Raw).Trim()) { throw 'Updater relaunch version is missing.' }
$UpdatedProcesses = Get-CimInstance Win32_Process -Filter "Name = 'JARVIS-OMEGA-V7.exe'" | Where-Object { $_.ExecutablePath -eq $InstalledExe }
if (-not $UpdatedProcesses) { throw 'Updated desktop is no longer running.' }
$UpdatedProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ([IO.File]::ReadAllText($EnvFile) -ne $CurrentEnv -or [IO.File]::ReadAllText($DataFile) -ne $CurrentData) { throw 'Relaunch update changed current user state.' }
Write-Host 'Installer, desktop shortcut, in-place update, data preservation and installed desktop launch PASS.'

# Reject a mismatched candidate version after installation, then prove rollback
# restored the executable while keeping settings and user data unchanged.
$BeforeHash = (Get-FileHash -LiteralPath $InstalledExe -Algorithm SHA256).Hash
& $PowerShell -NoProfile -NonInteractive -File .\scripts\apply-update.ps1 -Installer $Installer -AppDir $InstallDir -ParentId 0 -Sha256 $Hash -NoRelaunch -ExpectedVersion '0.0.0'
$RollbackCode = $LASTEXITCODE
Get-Content (Join-Path (Split-Path -Parent $Installer) 'update-result.txt')
if ($RollbackCode -eq 0) { throw 'Wrong candidate version was incorrectly accepted.' }
if ((Get-FileHash -LiteralPath $InstalledExe -Algorithm SHA256).Hash -ne $BeforeHash) { throw 'Rollback did not restore previous executable.' }
$Journal = Get-Content -LiteralPath ($InstallDir + '.rollback\checkpoint.json') -Raw | ConvertFrom-Json
if ($Journal.state -ne 'rolled_back') { throw 'Rollback checkpoint state is incorrect.' }
if ([IO.File]::ReadAllText($EnvFile) -ne $CurrentEnv -or [IO.File]::ReadAllText($DataFile) -ne $CurrentData) { throw 'Rollback touched current user state.' }
Write-Host 'Candidate mismatch / binary rollback / data preservation PASS.'
# The last native helper intentionally exited 1 for the rejected candidate.
# Every assertion above must pass before the test harness itself exits success.
exit 0
