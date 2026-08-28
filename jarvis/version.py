from __future__ import annotations

import re

# Single application release authority. Runtime configuration, diagnostics,
# packaging and installer metadata must derive from this value.
APP_VERSION = '8.0.0-rc2'

_VERSION_RE = re.compile(r'^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-rc(?P<rc>\d+))?$')


def windows_file_version(version: str = APP_VERSION) -> str:
    """Convert the release version to Windows' numeric a.b.c.d format."""
    match = _VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(f'Unsupported application version format: {version!r}')
    rc = int(match.group('rc') or 0)
    return '.'.join((match.group('major'), match.group('minor'), match.group('patch'), str(rc)))


WINDOWS_FILE_VERSION = windows_file_version()

__all__ = ['APP_VERSION', 'WINDOWS_FILE_VERSION', 'windows_file_version']
