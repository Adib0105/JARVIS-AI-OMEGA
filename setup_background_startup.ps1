param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Startup = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $Startup 'JARVIS OMEGA Background.lnk'
if ($Remove) {
    Remove-Item -LiteralPath $ShortcutPath -ErrorAction SilentlyContinue
    Write-Host 'JARVIS sign-in startup removed. The current app remains under your control.'
    exit 0
}
$Exe = Join-Path $Root 'JARVIS-OMEGA-V7.exe'
$Arguments = '--background'
if (-not (Test-Path -LiteralPath $Exe)) {
    $Exe = Join-Path $Root '.venv\Scripts\pythonw.exe'
    $Script = Join-Path $Root 'desktop_app.py'
    if (-not (Test-Path -LiteralPath $Exe) -or -not (Test-Path -LiteralPath $Script)) {
        throw 'Run setup_windows.ps1 first, or run this script beside the packaged JARVIS executable.'
    }
    $Arguments = '"' + $Script + '" --background'
}
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Exe
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = 'JARVIS background wake listener (enable in Background / Weather settings first)'
$Shortcut.Save()
Write-Host 'JARVIS will start at Windows sign-in. Enable Background / Weather once in the app. Use -Remove to undo.'
