param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][int]$ParentId,
    [Parameter(Mandatory=$true)][string]$Sha256,
    [switch]$NoRelaunch,
    [string]$ReadyFile = '',
    [string]$ExpectedVersion = ''
)
$ErrorActionPreference = 'Stop'
$AppDir = [IO.Path]::GetFullPath($AppDir).TrimEnd('\')
$Log = Join-Path (Split-Path -Parent $Installer) 'update-result.txt'
$Backup = $AppDir + '.rollback'
$Owned = @('JARVIS-OMEGA-V7.exe', '_internal', 'apply-update.ps1')
$Touched = $false
$InstallFinished = $false
$Desktop = $null
$UpdateLock = $null
function Save-State([string]$State) {
    @{ state=$State; app=$AppDir; sha256=$Sha256; time=(Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Backup 'checkpoint.json') -Encoding UTF8
}
function Copy-Owned([string]$Source, [string]$Target) {
    foreach ($Name in $Owned) {
        $From = Join-Path $Source $Name
        if (Test-Path -LiteralPath $From) {
            $Items = @((Get-Item -LiteralPath $From)) + @(Get-ChildItem -LiteralPath $From -Recurse -Force)
            if ($Items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
                throw 'Linked application files cannot be checkpointed safely.'
            }
            Copy-Item -LiteralPath $From -Destination (Join-Path $Target $Name) -Recurse -Force
        }
    }
}
function Get-OwnedManifest([string]$Root) {
    $Rows = foreach ($Name in $Owned) {
        $From = Join-Path $Root $Name
        if (Test-Path -LiteralPath $From) {
            $Items = @((Get-Item -LiteralPath $From)) + @(Get-ChildItem -LiteralPath $From -Recurse -Force)
            if ($Items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw 'Linked files are not valid checkpoint contents.' }
            foreach ($Item in ($Items | Where-Object { -not $_.PSIsContainer })) {
                [PSCustomObject]@{ path=$Item.FullName.Substring($Root.Length + 1); sha256=(Get-FileHash -LiteralPath $Item.FullName -Algorithm SHA256).Hash; size=$Item.Length }
            }
        }
    }
    return @($Rows | Sort-Object path)
}
function Assert-Manifest([string]$Root, $Expected) {
    $Actual = @(Get-OwnedManifest $Root)
    if (($Actual | ConvertTo-Json -Compress) -ne ($Expected | ConvertTo-Json -Compress)) { throw 'Application checkpoint file/hash inventory differs.' }
}
try {
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw 'Installer file is missing.' }
    if (-not (Test-Path -LiteralPath (Join-Path $AppDir $Owned[0]))) { throw 'Application folder is invalid.' }
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ne $Sha256) { throw 'Installer checksum changed.' }
    $UpdateLock = [IO.File]::Open(($AppDir + '.update.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if ($ReadyFile) { 'ready' | Set-Content -LiteralPath $ReadyFile }
    if ($ParentId -gt 0 -and (Get-Process -Id $ParentId -ErrorAction SilentlyContinue)) {
        Wait-Process -Id $ParentId -Timeout 60 -ErrorAction Stop
    }
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ne $Sha256) { throw 'Installer checksum changed. Update aborted.' }
    if (Test-Path -LiteralPath $Backup) {
        $Journal = Join-Path $Backup 'checkpoint.json'
        if (-not (Test-Path -LiteralPath $Journal)) { throw 'Previous update checkpoint needs operator review.' }
        $Previous = Get-Content -LiteralPath $Journal -Raw | ConvertFrom-Json
        if ($Previous.state -notin @('healthy', 'rolled_back')) { throw 'Interrupted update detected. Preserve the rollback folder and recover it before another update.' }
        Remove-Item -LiteralPath $Backup -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Backup | Out-Null
    $Manifest = @(Get-OwnedManifest $AppDir)
    Copy-Owned $AppDir $Backup
    Assert-Manifest $Backup $Manifest
    ConvertTo-Json -InputObject $Manifest -Depth 3 | Set-Content -LiteralPath (Join-Path $Backup 'files.json') -Encoding UTF8
    $BeforeHash = (Get-FileHash -LiteralPath (Join-Path $AppDir $Owned[0]) -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath (Join-Path $Backup $Owned[0]) -Algorithm SHA256).Hash -ne $BeforeHash) { throw 'Rollback checkpoint validation failed.' }
    $BeforeHash | Set-Content -LiteralPath (Join-Path $Backup 'previous-exe.sha256')
    Save-State 'prepared'
    $Args = @('/SP-', '/SILENT', '/NORESTART', '/NOCLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS', '/SUPPRESSMSGBOXES', ('/DIR="' + $AppDir + '"'), '/MERGETASKS=desktopicon', ('/LOG="' + $Log + '.install.log"'))
    $Process = Start-Process -FilePath $Installer -ArgumentList $Args -PassThru
    $Touched = $true
    Save-State 'installing'
    if (-not $Process.WaitForExit(300000)) { throw 'Installer is still running. Recovery checkpoint retained; wait for it before restoring.' }
    $InstallFinished = $true
    if ($Process.ExitCode -ne 0) { throw ('Installer failed with code ' + $Process.ExitCode) }
    # Candidate health occurs before any ordinary login/profile migration.
    $Health = $Log + '.candidate-health.json'
    Remove-Item -LiteralPath $Health -ErrorAction SilentlyContinue
    $Probe = Start-Process -FilePath (Join-Path $AppDir $Owned[0]) -WorkingDirectory $AppDir -ArgumentList @('--jarvis-update-health', ('"' + $Health + '"')) -PassThru
    if (-not $Probe.WaitForExit(45000)) { $Probe.Kill(); $Probe.WaitForExit(); throw 'Candidate health check timed out.' }
    if ($Probe.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $Health)) { throw 'Candidate health check failed.' }
    $Evidence = Get-Content -LiteralPath $Health -Raw | ConvertFrom-Json
    if (-not $Evidence.ok -or $Evidence.schema -ne 7) { throw 'Candidate health/schema compatibility failed.' }
    if ($ExpectedVersion -and $Evidence.version -ne $ExpectedVersion) { throw 'Candidate version differs from the downloaded release.' }
    if (-not $NoRelaunch) {
        $Ready = $Log + '.desktop-ready'
        Remove-Item -LiteralPath $Ready -ErrorAction SilentlyContinue
        $env:JARVIS_UPDATE_READY_FILE = $Ready
        try {
            $Desktop = Start-Process -FilePath (Join-Path $AppDir $Owned[0]) -WorkingDirectory $AppDir -PassThru
        } finally {
            Remove-Item Env:JARVIS_UPDATE_READY_FILE -ErrorAction SilentlyContinue
        }
        $Deadline = (Get-Date).AddSeconds(45)
        while ((Get-Date) -lt $Deadline -and -not (Test-Path -LiteralPath $Ready)) {
            $Desktop.Refresh()
            if ($Desktop.HasExited) { throw ('Updated desktop exited before readiness: ' + $Desktop.ExitCode) }
            Start-Sleep -Milliseconds 250
        }
        if (-not (Test-Path -LiteralPath $Ready)) { throw 'Updated desktop did not acknowledge startup.' }
        if ((Get-Content -LiteralPath $Ready -Raw).Trim() -ne $Evidence.version) { throw 'Desktop readiness version mismatch.' }
    }
    Save-State 'healthy'
    ('Update installed; candidate health passed; desktop version ' + $Evidence.version + '; previous binaries retained at ' + $Backup) | Set-Content -LiteralPath $Log
} catch {
    $Reason = $_.Exception.Message
    if ($Desktop) {
        $Desktop.Refresh()
        if (-not $Desktop.HasExited) { $Desktop.Kill(); $Desktop.WaitForExit() }
    }
    if ($Touched -and $InstallFinished) {
        try {
            $Manifest = @(Get-Content -LiteralPath (Join-Path $Backup 'files.json') -Raw | ConvertFrom-Json)
            Assert-Manifest $Backup $Manifest
            foreach ($Name in $Owned) {
                $Target = Join-Path $AppDir $Name
                if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
            }
            Copy-Owned $Backup $AppDir
            Assert-Manifest $AppDir $Manifest
            $ExpectedHash = (Get-Content -LiteralPath (Join-Path $Backup 'previous-exe.sha256') -Raw).Trim()
            if ((Get-FileHash -LiteralPath (Join-Path $AppDir $Owned[0]) -Algorithm SHA256).Hash -ne $ExpectedHash) { throw 'Restored executable hash mismatch.' }
            Save-State 'rolled_back'
            $Reason += ' Previous application binaries restored. Start JARVIS manually; no automatic retry will run.'
        } catch {
            $Reason += ' Automatic restore failed; preserve checkpoint at ' + $Backup + ' for manual recovery.'
        }
    }
    $Reason | Set-Content -LiteralPath $Log
    if (-not $NoRelaunch -and $env:CI -ne 'true') {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(('Update needs attention. Data/settings were not restored or deleted. Details: ' + $Log), 'JARVIS update') | Out-Null
    }
    exit 1
} finally {
    if ($UpdateLock) { $UpdateLock.Dispose() }
}
exit 0
