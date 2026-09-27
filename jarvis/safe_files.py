"""Bounded handle-based reads shared by text, document and indexing entry points."""
from __future__ import annotations

import os
import stat
from pathlib import Path

MAX_INPUT_BYTES = 2_000_000


def _windows_handle_path(fd):
    import ctypes
    import msvcrt
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
    api.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    api.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    size = api(msvcrt.get_osfhandle(fd), buffer, len(buffer), 0)
    if not size or size >= len(buffer):
        raise OSError('Cannot validate opened file identity.')
    value = buffer.value
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)


def read_bounded(files, file_path, extensions, limit=MAX_INPUT_BYTES):
    original = Path(file_path).expanduser().absolute()
    # Reject links before resolution, including Windows junctions/reparse points.
    for component in (original, *original.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise PermissionError('Linked/reparse document paths are not supported.')
    path = original.resolve()
    if not files._is_inside_root(path):
        raise PermissionError('File is outside approved roots.')
    if files._looks_secret(path):
        raise PermissionError('Secret-like path is blocked.')
    if path.suffix.lower() not in extensions:
        raise PermissionError(f'Unsupported file type: {path.suffix or "no extension"}')
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    if os.name == 'nt':
        # Alternate streams and device paths must never enter a text/parser API.
        if ':' in str(path)[len(path.drive):] or str(original).startswith(('\\\\.\\', '\\\\?\\')):
            raise PermissionError('Device paths and alternate streams are blocked.')
        fd = os.open(path, flags | getattr(os, 'O_BINARY', 0))
    else:
        # Walk using directory descriptors, so a parent-directory swap cannot
        # redirect the final open outside the path whose components we checked.
        directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in path.parts[1:-1]:
                next_dir = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = next_dir
            fd = os.open(path.name, flags, dir_fd=directory)
        finally:
            os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Only regular files up to 2 MB may be read.')
        if os.name == 'nt':
            actual = _windows_handle_path(stream.fileno()).resolve()
            if actual != path or not files._is_inside_root(actual) or files._looks_secret(actual):
                raise PermissionError('Opened file identity changed.')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > limit or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('File grew or changed during reading; retry with a stable file.')
    return path, info, raw
