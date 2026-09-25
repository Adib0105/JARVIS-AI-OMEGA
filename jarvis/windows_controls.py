"""Allowlisted Windows power controls for the permission-gated tool runtime."""
from __future__ import annotations

import os

from .automation import _pyautogui


WINDOWS_CONTROL_ACTIONS = (
    'volume_up',
    'volume_down',
    'volume_mute',
    'media_play_pause',
    'media_next',
    'media_previous',
    'show_desktop',
    'switch_window',
    'minimize_window',
    'maximize_window',
    'close_window',
    'new_virtual_desktop',
    'next_virtual_desktop',
    'previous_virtual_desktop',
    'lock_pc',
    'open_wifi_settings',
    'open_bluetooth_settings',
    'open_display_settings',
    'open_sound_settings',
    'open_apps_settings',
)


_KEYS = {
    'volume_up': 'volumeup',
    'volume_down': 'volumedown',
    'volume_mute': 'volumemute',
    'media_play_pause': 'playpause',
    'media_next': 'nexttrack',
    'media_previous': 'prevtrack',
}

_HOTKEYS = {
    'show_desktop': ('win', 'd'),
    'switch_window': ('alt', 'tab'),
    'minimize_window': ('win', 'down'),
    'maximize_window': ('win', 'up'),
    'close_window': ('alt', 'f4'),
    'new_virtual_desktop': ('ctrl', 'win', 'd'),
    'next_virtual_desktop': ('ctrl', 'win', 'right'),
    'previous_virtual_desktop': ('ctrl', 'win', 'left'),
}

_SETTINGS = {
    'open_wifi_settings': 'ms-settings:network-wifi',
    'open_bluetooth_settings': 'ms-settings:bluetooth',
    'open_display_settings': 'ms-settings:display',
    'open_sound_settings': 'ms-settings:sound',
    'open_apps_settings': 'ms-settings:appsfeatures',
}


def windows_control(action: str) -> dict:
    """Execute one exact allowlisted action; arbitrary shell input is impossible."""
    if os.name != 'nt':
        raise RuntimeError('Windows Power Pack is available on Windows only.')
    action = str(action or '').strip().lower()
    if action not in WINDOWS_CONTROL_ACTIONS:
        raise ValueError('Unsupported Windows action. Allowed: ' + ', '.join(WINDOWS_CONTROL_ACTIONS))

    if action in _KEYS:
        _pyautogui().press(_KEYS[action])
    elif action in _HOTKEYS:
        _pyautogui().hotkey(*_HOTKEYS[action])
    elif action in _SETTINGS:
        os.startfile(_SETTINGS[action])  # type: ignore[attr-defined]
    elif action == 'lock_pc':
        import ctypes
        if not ctypes.windll.user32.LockWorkStation():  # type: ignore[attr-defined]
            raise OSError('Windows did not accept the lock-workstation request.')
    else:  # pragma: no cover - guarded by the complete action table above.
        raise ValueError(action)

    # Keyboard/media shortcuts do not expose a trustworthy application
    # postcondition.  Be explicit instead of claiming an unverified outcome.
    return {
        'action': action,
        'status': 'REQUESTED',
        'verified': action == 'lock_pc',
        'message': 'Windows accepted the requested control action.',
    }

