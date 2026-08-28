from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path


APP_COMMANDS = {
    'notepad': ['notepad.exe'],
    'calculator': ['calc.exe'],
    'calc': ['calc.exe'],
    'explorer': ['explorer.exe'],
    'paint': ['mspaint.exe'],
    'task manager': ['taskmgr.exe'],
    'taskmgr': ['taskmgr.exe'],
    'vscode': ['code.exe'],
    'vs code': ['code.exe'],
    'visual studio code': ['code.exe'],
    'chrome': ['chrome.exe'],
    'google chrome': ['chrome.exe'],
    'edge': ['msedge.exe'],
    'microsoft edge': ['msedge.exe'],
}


_COMMON_WINDOWS_APP_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    'chrome.exe': (
        ('LOCALAPPDATA', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ('PROGRAMFILES', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ('PROGRAMFILES(X86)', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ),
    'msedge.exe': (
        ('PROGRAMFILES(X86)', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        ('PROGRAMFILES', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        ('LOCALAPPDATA', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ),
    'code.exe': (
        ('LOCALAPPDATA', 'Programs', 'Microsoft VS Code', 'Code.exe'),
        ('PROGRAMFILES', 'Microsoft VS Code', 'Code.exe'),
        ('PROGRAMFILES(X86)', 'Microsoft VS Code', 'Code.exe'),
    ),
}


def system_info() -> dict:
    return {
        'os': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python': sys.version.split()[0],
        'hostname': platform.node(),
        'cwd': str(Path.cwd()),
        'user': os.getenv('USERNAME') or os.getenv('USER') or '',
    }


def system_metrics() -> dict:
    try:
        import psutil

        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home().anchor or '/'))
        battery = psutil.sensors_battery()
        net = psutil.net_io_counters()
        return {
            'cpu_percent': round(psutil.cpu_percent(interval=None), 1),
            'memory_percent': round(vm.percent, 1),
            'memory_available_gb': round(vm.available / (1024 ** 3), 2),
            'disk_percent': round(disk.percent, 1),
            'battery_percent': round(battery.percent, 1) if battery else None,
            'battery_plugged': bool(battery.power_plugged) if battery else None,
            'processes': len(psutil.pids()),
            'network_sent_mb': round(net.bytes_sent / (1024 ** 2), 1),
            'network_received_mb': round(net.bytes_recv / (1024 ** 2), 1),
        }
    except Exception as exc:
        return {'available': False, 'error': str(exc)}


def current_time() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def open_url(url: str) -> str:
    if not url.lower().startswith(('http://', 'https://')):
        raise ValueError('Only http/https URLs are allowed.')
    ok = webbrowser.open(url, new=2)
    return 'Opened URL.' if ok else 'Browser launch was requested.'


def _registry_app_path(executable: str) -> str | None:
    """Resolve a Windows App Paths registration without invoking a shell."""
    if os.name != 'nt':
        return None
    try:
        import winreg
    except Exception:
        return None

    key_path = rf'Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}'
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    views = [0]
    for flag_name in ('KEY_WOW64_64KEY', 'KEY_WOW64_32KEY'):
        flag = getattr(winreg, flag_name, 0)
        if flag and flag not in views:
            views.append(flag)

    for root in roots:
        for view in views:
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, None)
            except OSError:
                continue
            candidate = os.path.expandvars(str(value).strip().strip('"'))
            if candidate and Path(candidate).is_file():
                return str(Path(candidate))
    return None


def _common_windows_app_path(executable: str) -> str | None:
    for parts in _COMMON_WINDOWS_APP_PATHS.get(executable.lower(), ()): 
        base = os.environ.get(parts[0], '').strip()
        if not base:
            continue
        candidate = Path(base).joinpath(*parts[1:])
        if candidate.is_file():
            return str(candidate)
    return None


def _resolve_executable(executable: str) -> str | None:
    """Find an allowlisted executable using PATH, App Paths and common install roots."""
    discovered = shutil.which(executable)
    if discovered:
        return discovered
    registered = _registry_app_path(executable)
    if registered:
        return registered
    return _common_windows_app_path(executable)


def _resolve_app_command(app: str) -> list[str]:
    key = app.strip().lower()
    command = APP_COMMANDS.get(key)
    if not command:
        raise PermissionError(f"App '{app}' is not in the allowlist: {', '.join(sorted(APP_COMMANDS))}")
    resolved = _resolve_executable(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return list(command)


def open_app(app: str) -> str:
    if os.name != 'nt':
        raise RuntimeError('App launching is currently configured for Windows.')
    key = app.strip().lower()
    command = _resolve_app_command(key)
    try:
        subprocess.Popen(command, shell=False)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"'{key}' is allowlisted, but Windows could not find its executable in PATH, "
            'registered App Paths, or known install locations.'
        ) from exc
    return f'Opened {key}.'


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
