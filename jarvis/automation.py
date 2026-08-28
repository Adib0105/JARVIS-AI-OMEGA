from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path


def browser_search(query: str, engine: str = 'google') -> str:
    query = query.strip()
    if not query:
        raise ValueError('Search query is empty.')
    engines = {
        'google': 'https://www.google.com/search?q=',
        'bing': 'https://www.bing.com/search?q=',
        'youtube': 'https://www.youtube.com/results?search_query=',
        'github': 'https://github.com/search?q=',
    }
    key = engine.strip().lower()
    if key not in engines:
        raise ValueError(f"Unsupported engine. Use: {', '.join(engines)}")
    url = engines[key] + urllib.parse.quote_plus(query)
    webbrowser.open(url, new=2)
    return f'Opened {key} search for: {query}'


def _pyautogui():
    try:
        import pyautogui
    except Exception as exc:
        raise RuntimeError('Desktop automation package pyautogui is unavailable. Run setup_windows.ps1.') from exc
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.08
    return pyautogui


def type_text(text: str, interval: float = 0.02) -> str:
    if len(text) > 5000:
        raise ValueError('Refusing to type more than 5000 characters in one action.')
    pg = _pyautogui()
    pg.write(text, interval=max(0.0, min(float(interval), 0.2)))
    return f'Typed {len(text)} characters.'


def press_key(key: str) -> str:
    key = key.strip().lower()
    allowed = {
        'enter', 'tab', 'esc', 'escape', 'space', 'backspace', 'delete', 'home', 'end',
        'pageup', 'pagedown', 'up', 'down', 'left', 'right', 'f5', 'f11',
        'volumeup', 'volumedown', 'volumemute',
    }
    if key not in allowed:
        raise PermissionError(f"Key '{key}' is not allowlisted.")
    _pyautogui().press(key)
    return f'Pressed {key}.'


def hotkey(keys: list[str]) -> str:
    clean = [str(k).strip().lower() for k in keys if str(k).strip()]
    if not 2 <= len(clean) <= 4:
        raise ValueError('Hotkey requires 2 to 4 keys.')
    allowed = {
        'ctrl', 'shift', 'alt', 'win', 'enter', 'tab', 'esc', 'space', 'a', 'c', 'f', 'l',
        'n', 'p', 'r', 's', 't', 'v', 'w', 'x', 'z', 'f5', 'f11',
    }
    if any(k not in allowed for k in clean):
        raise PermissionError('One or more hotkey keys are not allowlisted.')
    _pyautogui().hotkey(*clean)
    return 'Pressed hotkey: ' + '+'.join(clean)


def click_screen(x: int, y: int, button: str = 'left') -> str:
    button = button.strip().lower()
    if button not in {'left', 'right'}:
        raise ValueError('button must be left or right.')
    pg = _pyautogui()
    width, height = pg.size()
    x, y = int(x), int(y)
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f'Click coordinate outside screen bounds {width}x{height}.')
    pg.click(x=x, y=y, button=button)
    return f'Clicked {button} at ({x}, {y}).'


def open_local_path(path: str) -> str:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    if os.name == 'nt':
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(target)], shell=False)
    else:
        subprocess.Popen(['xdg-open', str(target)], shell=False)
    return f'Opened {target}.'
