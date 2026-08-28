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
    'notepad': ['notepad.exe'], 'calculator': ['calc.exe'], 'calc': ['calc.exe'],
    'explorer': ['explorer.exe'], 'paint': ['mspaint.exe'], 'task manager': ['taskmgr.exe'],
    'taskmgr': ['taskmgr.exe'], 'vscode': ['code.exe'], 'vs code': ['code.exe'],
    'visual studio code': ['code.exe'], 'chrome': ['chrome.exe'], 'google chrome': ['chrome.exe'],
    'edge': ['msedge.exe'], 'microsoft edge': ['msedge.exe'],
}

APP_URIS = {
    'settings': 'ms-settings:',
    'windows settings': 'ms-settings:',
    'bluetooth settings': 'ms-settings:bluetooth',
    'wifi settings': 'ms-settings:network-wifi',
    'network settings': 'ms-settings:network',
    'display settings': 'ms-settings:display',
    'sound settings': 'ms-settings:sound',
    'apps settings': 'ms-settings:appsfeatures',
    'windows update': 'ms-settings:windowsupdate',
}

_COMMON_WINDOWS_APP_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    'chrome.exe': (('LOCALAPPDATA', 'Google', 'Chrome', 'Application', 'chrome.exe'), ('PROGRAMFILES', 'Google', 'Chrome', 'Application', 'chrome.exe'), ('PROGRAMFILES(X86)', 'Google', 'Chrome', 'Application', 'chrome.exe')),
    'msedge.exe': (('PROGRAMFILES(X86)', 'Microsoft', 'Edge', 'Application', 'msedge.exe'), ('PROGRAMFILES', 'Microsoft', 'Edge', 'Application', 'msedge.exe'), ('LOCALAPPDATA', 'Microsoft', 'Edge', 'Application', 'msedge.exe')),
    'code.exe': (('LOCALAPPDATA', 'Programs', 'Microsoft VS Code', 'Code.exe'), ('PROGRAMFILES', 'Microsoft VS Code', 'Code.exe'), ('PROGRAMFILES(X86)', 'Microsoft VS Code', 'Code.exe')),
}


def system_info() -> dict:
    return {'os': platform.platform(), 'machine': platform.machine(), 'processor': platform.processor(), 'python': sys.version.split()[0], 'hostname': platform.node(), 'cwd': str(Path.cwd()), 'user': os.getenv('USERNAME') or os.getenv('USER') or ''}


def system_metrics() -> dict:
    try:
        import psutil
    except Exception as exc:
        return {'available': False, 'error': f'psutil unavailable: {type(exc).__name__}'}

    warnings: list[str] = []

    def probe(name: str, operation, default=None):
        try:
            return operation()
        except Exception as exc:
            warnings.append(f'{name}:{type(exc).__name__}')
            return default

    cpu = probe('cpu', lambda: round(psutil.cpu_percent(interval=None), 1))
    memory = probe('memory', psutil.virtual_memory)
    disk = probe('disk', lambda: psutil.disk_usage(str(Path.home().anchor or os.sep)))
    battery = probe('battery', psutil.sensors_battery)
    network = probe('network', psutil.net_io_counters)
    process_ids = probe('processes', psutil.pids, [])

    core_available = cpu is not None and memory is not None and disk is not None
    result = {
        'available': core_available,
        'cpu_percent': cpu,
        'memory_percent': round(memory.percent, 1) if memory is not None else None,
        'memory_available_gb': round(memory.available / (1024 ** 3), 2) if memory is not None else None,
        'disk_percent': round(disk.percent, 1) if disk is not None else None,
        'battery_percent': round(battery.percent, 1) if battery else None,
        'battery_plugged': bool(battery.power_plugged) if battery else None,
        'processes': len(process_ids),
        'network_sent_mb': round(network.bytes_sent / (1024 ** 2), 1) if network else None,
        'network_received_mb': round(network.bytes_recv / (1024 ** 2), 1) if network else None,
    }
    if warnings:
        result['warnings'] = warnings
    if not core_available:
        result['error'] = 'One or more core system metrics are unavailable.'
    return result


def current_time() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def open_url(url: str) -> str:
    if not url.lower().startswith(('http://', 'https://')): raise ValueError('Only http/https URLs are allowed.')
    ok = webbrowser.open(url, new=2)
    return 'Opened URL.' if ok else 'Browser launch was requested.'


def _registry_app_path(executable: str) -> str | None:
    if os.name != 'nt': return None
    try: import winreg
    except Exception: return None
    key_path = rf'Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}'
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE); views = [0]
    for flag_name in ('KEY_WOW64_64KEY', 'KEY_WOW64_32KEY'):
        flag = getattr(winreg, flag_name, 0)
        if flag and flag not in views: views.append(flag)
    for root in roots:
        for view in views:
            try:
                with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key: value, _ = winreg.QueryValueEx(key, None)
            except OSError: continue
            candidate = os.path.expandvars(str(value).strip().strip('"'))
            if candidate and Path(candidate).is_file(): return str(Path(candidate))
    return None


def _common_windows_app_path(executable: str) -> str | None:
    for parts in _COMMON_WINDOWS_APP_PATHS.get(executable.lower(), ()):
        base = os.environ.get(parts[0], '').strip()
        if not base: continue
        candidate = Path(base).joinpath(*parts[1:])
        if candidate.is_file(): return str(candidate)
    return None


def _resolve_executable(executable: str) -> str | None:
    return shutil.which(executable) or _registry_app_path(executable) or _common_windows_app_path(executable)


def _resolve_app_command(app: str) -> list[str]:
    key = app.strip().lower(); command = APP_COMMANDS.get(key)
    if not command: raise PermissionError(f"App '{app}' is not in the allowlist: {', '.join(sorted(set(APP_COMMANDS) | set(APP_URIS)))}")
    resolved = _resolve_executable(command[0]); return [resolved, *command[1:]] if resolved else list(command)


def open_app(app: str) -> str:
    if os.name != 'nt': raise RuntimeError('App launching is currently configured for Windows.')
    key = app.strip().lower()
    uri = APP_URIS.get(key)
    if uri:
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError(f'Windows could not open {key}.') from exc
        return f'Opened {key}.'
    command = _resolve_app_command(key)
    try: subprocess.Popen(command, shell=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"'{key}' is allowlisted, but Windows could not find its executable in PATH, registered App Paths, or known install locations.") from exc
    return f'Opened {key}.'


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
