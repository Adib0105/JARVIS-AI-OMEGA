from __future__ import annotations

import json
import urllib.error
import urllib.request

RELEASE_API = 'https://api.github.com/repos/Adib0105/JARVIS-AI-OMEGA/releases/latest'


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip('v')
    parts = []
    for token in clean.split('.'):
        digits = ''.join(ch for ch in token if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts or [0])


def check_latest_release(current_version: str, timeout: float = 8.0) -> dict:
    request = urllib.request.Request(
        RELEASE_API,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'JARVIS-AI-OMEGA-V6'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {'available': False, 'published': False, 'message': 'No GitHub Release has been published yet.'}
        raise RuntimeError(f'GitHub update check failed: HTTP {exc.code}') from exc
    except Exception as exc:
        raise RuntimeError(f'GitHub update check failed: {exc}') from exc

    tag = str(payload.get('tag_name') or '').strip()
    url = str(payload.get('html_url') or '').strip()
    newer = _version_tuple(tag) > _version_tuple(current_version)
    return {
        'available': newer,
        'published': True,
        'current_version': current_version,
        'latest_version': tag,
        'url': url,
        'name': payload.get('name') or tag,
        'message': f'New version {tag} available.' if newer else f'You are up to date ({current_version}).',
    }
