param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][int]$ParentId,
    [Parameter(Mandatory=$true)][string]$Sha256,
    [switch]$NoRelaunch,
    [string]$ReadyFile = ''
)
$ErrorActionPreference = 'Stop'
$Log = Join-Path (Split-Path -Parent $Installer) 'update-result.txt'
try {
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw 'Installer file is missing.' }
    if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'JARVIS-OMEGA-V7.exe'))) { throw 'Application folder is invalid.' }
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ne $Sha256) { throw 'Installer checksum changed.' }
    if ($ReadyFile) { 'ready' | Set-Content -LiteralPath $ReadyFile }
    # Do not force-kill the assistant or any other application.
    if ($ParentId -gt 0 -and (Get-Process -Id $ParentId -ErrorAction SilentlyContinue)) {
        Wait-Process -Id $ParentId -Timeout 60 -ErrorAction Stop
    }
    if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ne $Sha256) {
        throw 'Installer checksum changed. Update aborted.'
    }
    $Args = @('/SP-', '/SILENT', '/NORESTART', '/NOCLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS', '/SUPPRESSMSGBOXES', ('/DIR="' + $AppDir + '"'), '/MERGETASKS=desktopicon', ('/LOG="' + $Log + '.install.log"'))
    $Process = Start-Process -FilePath $Installer -ArgumentList $Args -PassThru
    if (-not $Process.WaitForExit(300000)) { throw 'Installer is still running. Check its window before retrying.' }
    if ($Process.ExitCode -ne 0) { throw ('Installer failed with code ' + $Process.ExitCode + '. Check the install log beside this file.') }
    'Update installed successfully.' | Set-Content -LiteralPath $Log
    if (-not $NoRelaunch) {
        $Ready = $Log + '.desktop-ready'
        Remove-Item -LiteralPath $Ready -ErrorAction SilentlyContinue
        $env:JARVIS_UPDATE_READY_FILE = $Ready
        try {
            $Desktop = Start-Process -FilePath (Join-Path $AppDir 'JARVIS-OMEGA-V7.exe') -WorkingDirectory $AppDir -PassThru
        } finally {
            Remove-Item Env:JARVIS_UPDATE_READY_FILE -ErrorAction SilentlyContinue
        }
        $Deadline = (Get-Date).AddSeconds(45)
        while ((Get-Date) -lt $Deadline) {
            if (Test-Path -LiteralPath $Ready) {
                $Version = (Get-Content -LiteralPath $Ready -Raw).Trim()
                ('Update installed; desktop started version ' + $Version) | Set-Content -LiteralPath $Log
                return
            }
            $Desktop.Refresh()
            if ($Desktop.HasExited) { throw ('Updated desktop exited before readiness (code ' + $Desktop.ExitCode + ').') }
            Start-Sleep -Milliseconds 250
        }
        throw 'Installer finished, but the updated desktop did not report readiness within 45 seconds.'
    }
} catch {
    $_.Exception.Message | Set-Content -LiteralPath $Log
    if (-not $NoRelaunch) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(('Update could not finish. Your data has not been deleted. Details: ' + $Log), 'JARVIS update') | Out-Null
    }
    exit 1
}

exit 0
