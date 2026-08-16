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
}


def system_info() -> dict:
    return {
        'os': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python': sys.version.split()[0],
        'hostname': platform.node(),
        'cwd': str(Path.cwd()),
    }


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
    subprocess.Popen(command)
    return f'Opened {key}.'


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
