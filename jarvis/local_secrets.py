"""Windows current-user DPAPI protection; no application password/key to ship.

Non-Windows development keeps existing owner-only file permissions; it does not
claim encryption. DPAPI does not isolate JARVIS profiles sharing one OS account.
"""
import base64
import os

PREFIX = 'dpapi:v1:'


def _crypt(raw, decrypt=False):
    import ctypes as c
    from ctypes import wintypes as w
    class Blob(c.Structure):
        _fields_ = [('size', w.DWORD), ('data', c.POINTER(c.c_ubyte))]
    buffer = (c.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, output = Blob(len(raw), buffer), Blob()
    crypt = c.WinDLL('crypt32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [c.POINTER(Blob), c.c_void_p, c.POINTER(Blob), c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(Blob)]
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [c.POINTER(Blob), w.LPCWSTR, c.POINTER(Blob), c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(Blob)]
    fn.restype = w.BOOL
    if not fn(c.byref(source), None, None, None, None, 1, c.byref(output)):
        raise RuntimeError('Windows could not unlock/protect this credential. Sign in again on this Windows account.')
    try:
        return c.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(c.cast(output.data, c.c_void_p))


def protect(value):
    if not value or str(value).startswith(PREFIX) or os.name != 'nt':
        return value
    return PREFIX + base64.b64encode(_crypt(str(value).encode('utf-8'))).decode('ascii')


def reveal(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    if os.name != 'nt':
        raise RuntimeError('This credential belongs to its original Windows account. Sign in again.')
    return _crypt(base64.b64decode(value[len(PREFIX):], validate=True), decrypt=True).decode('utf-8')
