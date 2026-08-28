from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

HOTKEY_JARVIS_ID = 0x4A41
HOTKEY_EMOJI_ID = 0x4A45
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_J = 0x4A
VK_E = 0x45
WM_HOTKEY = 0x0312
SW_RESTORE = 9
SW_SHOW = 5


def _find_jarvis_window() -> int:
    if os.name != 'nt':
        return 0
    user32 = ctypes.windll.user32
    found = ctypes.c_void_p(0)
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.upper()
        if 'JARVIS AI OMEGA' in title and 'PERMISSION GATE' not in title:
            found.value = int(hwnd)
            return False
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    return int(found.value or 0)


def show_jarvis_window() -> bool:
    """Restore/focus the existing JARVIS desktop window without launching a second app."""
    if os.name != 'nt':
        return False
    hwnd = _find_jarvis_window()
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True


def open_windows_emoji_panel() -> bool:
    """Open Windows' Unicode emoji picker (Win+.), which WhatsApp/Web can render."""
    if os.name != 'nt':
        return False
    user32 = ctypes.windll.user32
    VK_LWIN = 0x5B
    VK_OEM_PERIOD = 0xBE
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_OEM_PERIOD, 0, 0, 0)
    user32.keybd_event(VK_OEM_PERIOD, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    return True


def _hotkey_loop(stop_event: threading.Event) -> None:
    if os.name != 'nt':
        return
    user32 = ctypes.windll.user32
    registered_jarvis = bool(user32.RegisterHotKey(None, HOTKEY_JARVIS_ID, MOD_CONTROL | MOD_ALT, VK_J))
    registered_emoji = bool(user32.RegisterHotKey(None, HOTKEY_EMOJI_ID, MOD_CONTROL | MOD_ALT, VK_E))
    msg = wintypes.MSG()
    try:
        while not stop_event.is_set():
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY:
                    if msg.wParam == HOTKEY_JARVIS_ID:
                        show_jarvis_window()
                    elif msg.wParam == HOTKEY_EMOJI_ID:
                        open_windows_emoji_panel()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.04)
    finally:
        if registered_jarvis:
            user32.UnregisterHotKey(None, HOTKEY_JARVIS_ID)
        if registered_emoji:
            user32.UnregisterHotKey(None, HOTKEY_EMOJI_ID)


def start_global_hotkeys() -> threading.Event:
    """Enable desktop emoji support and global Ctrl+Alt+J / Ctrl+Alt+E hotkeys."""
    # Install before run_adaptive_gui constructs JarvisDesktop so both the composer
    # and chat body use the native Unicode emoji font and expose the in-app picker.
    try:
        from .emoji_support import install_emoji_support
        install_emoji_support()
    except Exception:
        # Emoji enhancement must never prevent the assistant itself from starting.
        pass

    stop_event = threading.Event()
    if os.name == 'nt':
        threading.Thread(
            target=_hotkey_loop,
            args=(stop_event,),
            daemon=True,
            name='jarvis-global-hotkeys',
        ).start()
    return stop_event


__all__ = [
    'HOTKEY_JARVIS_ID',
    'HOTKEY_EMOJI_ID',
    'open_windows_emoji_panel',
    'show_jarvis_window',
    'start_global_hotkeys',
]
