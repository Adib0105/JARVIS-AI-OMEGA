"""Prevent two desktop listeners competing for the same Windows microphone."""
import os

_handle = None


def acquire_desktop_instance():
    global _handle
    if os.name != 'nt':
        return True
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, 'Local\\JarvisOmegaDesktop')
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Could not initialize desktop instance lock.')
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel.CloseHandle(handle)
        return False
    _handle = handle  # Windows releases the handle on process exit.
    return True


def release_desktop_instance():
    """Release the per-user mutex before an intentional sign-out restart."""
    global _handle
    handle, _handle = _handle, None
    if os.name != 'nt' or not handle:
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CloseHandle(handle)


def show_existing_desktop():
    if os.name != 'nt':
        return False
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    handle = user.FindWindowW(None, 'JARVIS AI OMEGA V7 // RELIABLE ARC DESKTOP AGENT')
    if not handle:
        return False
    user.ShowWindow(handle, 9)
    user.SetForegroundWindow(handle)
    return True
