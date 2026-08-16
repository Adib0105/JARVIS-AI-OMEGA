from __future__ import annotations

import json
import os
import platform
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
    'vscode': ['code'],
    'vs code': ['code'],
    'chrome': ['chrome.exe'],
    'edge': ['msedge.exe'],
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


def open_app(app: str) -> str:
    if os.name != 'nt':
        raise RuntimeError('App launching is currently configured for Windows.')
    key = app.strip().lower()
    command = APP_COMMANDS.get(key)
    if not command:
        raise PermissionError(f"App '{app}' is not in the allowlist: {', '.join(sorted(APP_COMMANDS))}")
    try:
        subprocess.Popen(command, shell=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"'{key}' was allowlisted but Windows could not find its executable.") from exc
    return f'Opened {key}.'


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
