from __future__ import annotations

import json
import urllib.error
import urllib.request

from packaging.version import InvalidVersion, Version

from .version import APP_VERSION

RELEASE_API = 'https://api.github.com/repos/Adib0105/JARVIS-AI-OMEGA/releases/latest'


def _parse_version(value: str) -> Version:
    clean = str(value or '').strip()
    if clean.lower().startswith('v'):
        clean = clean[1:]
    try:
        return Version(clean)
    except InvalidVersion as exc:
        raise ValueError(f'Unsupported release version: {value!r}') from exc


def check_latest_release(current_version: str, timeout: float = 8.0) -> dict:
    request = urllib.request.Request(
        RELEASE_API,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': f'JARVIS-AI-OMEGA/{APP_VERSION}',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        if status == 404:
            return {'available': False, 'published': False, 'message': 'No GitHub Release has been published yet.'}
        raise RuntimeError(f'GitHub update check failed: HTTP {status}') from exc
    except Exception as exc:
        raise RuntimeError(f'GitHub update check failed: {exc}') from exc

    tag = str(payload.get('tag_name') or '').strip()
    url = str(payload.get('html_url') or '').strip()
    if not tag:
        raise RuntimeError('GitHub latest release did not include a tag_name.')
    try:
        newer = _parse_version(tag) > _parse_version(current_version)
    except ValueError as exc:
        raise RuntimeError(f'GitHub update check returned an unrecognized version: {tag!r}.') from exc

    return {
        'available': newer,
        'published': True,
        'current_version': current_version,
        'latest_version': tag,
        'url': url,
        'name': payload.get('name') or tag,
        'message': f'New version {tag} available.' if newer else f'You are up to date ({current_version}).',
    }
