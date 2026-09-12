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
& .\scripts\apply-update.ps1 -Installer $Installer -AppDir $InstallDir -ParentId 0 -Sha256 $Hash -NoRelaunch
if ($LASTEXITCODE -ne 0) { throw 'Update helper failed.' }
if ([IO.File]::ReadAllText($EnvFile) -ne $SavedEnv) { throw 'Update changed user environment settings.' }
if ((Get-Content $DataFile -Raw).Trim() -ne 'keep my data') { throw 'Update changed user data.' }
$Report = Join-Path (Get-Location) 'installed-desktop-smoke.json'
$p = Start-Process $InstalledExe -WorkingDirectory $env:TEMP -ArgumentList @('--jarvis-desktop-smoke', ('"' + $Report + '"')) -PassThru
if (-not $p.WaitForExit(60000)) { $p.Kill(); throw 'Installed desktop hung.' }
if ($p.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw 'Installed desktop failed.' }
if (-not (Get-Content $Report -Raw | ConvertFrom-Json).ok) { throw 'Installed desktop smoke failed.' }
Write-Host 'Installer, desktop shortcut, in-place update, data preservation and installed desktop launch PASS.'
