"""Exact Core Audio mute state; no toggle fallback when observation fails."""
from __future__ import annotations


def set_mute(desired: bool) -> bool:
    import ctypes as c
    import uuid
    from ctypes import wintypes as w
    if type(desired) is not bool:
        raise ValueError('Mute state must be boolean.')
    guid_type = c.c_ubyte * 16
    def guid(value):
        return guid_type.from_buffer_copy(uuid.UUID(value).bytes_le)
    ole = c.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [c.c_void_p, w.DWORD]
    ole.CoInitializeEx.restype = c.c_long
    ole.CoCreateInstance.argtypes = [c.POINTER(guid_type), c.c_void_p, w.DWORD, c.POINTER(guid_type), c.POINTER(c.c_void_p)]
    ole.CoCreateInstance.restype = c.c_long
    initialized = ole.CoInitializeEx(None, 2)
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE: existing apartment
        raise OSError('Windows audio COM initialization failed.')
    enumerator, device, endpoint = c.c_void_p(), c.c_void_p(), c.c_void_p()
    def method(ptr, index, *types):
        table = c.cast(ptr, c.POINTER(c.POINTER(c.c_void_p))).contents
        return c.WINFUNCTYPE(c.c_long, c.c_void_p, *types)(table[index])
    def check(result):
        if result < 0:
            raise OSError('Windows audio endpoint operation failed; mute state is unknown.')
    try:
        check(ole.CoCreateInstance(guid('BCDE0395-E52F-467C-8E3D-C4579291692E'), None, 1,
                                   guid('A95664D2-9614-4F35-A746-DE8DB63617E6'), c.byref(enumerator)))
        check(method(enumerator, 4, c.c_int, c.c_int, c.POINTER(c.c_void_p))(enumerator, 0, 0, c.byref(device)))
        check(method(device, 3, c.POINTER(guid_type), w.DWORD, c.c_void_p, c.POINTER(c.c_void_p))(
            device, guid('5CDF2C82-841E-4546-9722-0CF74078229A'), 23, None, c.byref(endpoint)))
        muted = w.BOOL()
        read = method(endpoint, 15, c.POINTER(w.BOOL))
        check(read(endpoint, c.byref(muted)))
        if bool(muted.value) != desired:
            check(method(endpoint, 14, w.BOOL, c.c_void_p)(endpoint, desired, None))
        check(read(endpoint, c.byref(muted)))
        if bool(muted.value) != desired:
            raise OSError('Windows mute readback differs from the requested state.')
        return bool(muted.value)
    finally:
        for ptr in (endpoint, device, enumerator):
            if ptr:
                method(ptr, 2)(ptr)
        if initialized >= 0:
            ole.CoUninitialize()


def request_media_state(playing: bool):
    import ctypes as c
    from ctypes import wintypes as w
    user = c.WinDLL('user32', use_last_error=True)
    user.GetForegroundWindow.restype = w.HWND
    user.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT, c.POINTER(c.c_size_t)]
    user.SendMessageTimeoutW.restype = w.LPARAM
    window = user.GetForegroundWindow()
    result = c.c_size_t()
    command = 46 if playing else 47  # APPCOMMAND_MEDIA_PLAY / MEDIA_PAUSE, never toggle
    if not window or not user.SendMessageTimeoutW(window, 0x319, window, command << 16, 2, 1000, c.byref(result)):
        raise OSError('Media application did not acknowledge the requested state.')
