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
