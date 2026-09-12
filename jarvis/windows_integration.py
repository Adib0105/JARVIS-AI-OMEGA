"""Per-user Windows shortcuts; no administrator or registry changes."""
import os
from pathlib import Path
import subprocess
import sys


def powershell_path():
    if os.name != 'nt':
        raise RuntimeError('This option is available on Windows only.')
    return str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')


def set_startup(enabled):
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Install the Windows build to manage sign-in startup.')
    # Paths are transported via environment variables, never interpolated into script code.
    env = dict(os.environ, JARVIS_SHORTCUT_TARGET=sys.executable, JARVIS_SHORTCUT_ENABLED=str(int(enabled)))
    code = '''$ErrorActionPreference = 'Stop'
$p = Join-Path ([Environment]::GetFolderPath('Startup')) 'JARVIS OMEGA Background.lnk'
if ($env:JARVIS_SHORTCUT_ENABLED -eq '0') { Remove-Item -LiteralPath $p -ErrorAction SilentlyContinue; exit }
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p)
$s.TargetPath = $env:JARVIS_SHORTCUT_TARGET
$s.Arguments = '--background'
$s.WorkingDirectory = Split-Path -Parent $env:JARVIS_SHORTCUT_TARGET
$s.Save()
'''
    subprocess.run([powershell_path(), '-NoProfile', '-NonInteractive', '-Command', code], env=env,
                   check=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
