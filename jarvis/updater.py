from __future__ import annotations

import http.client
import json
from urllib.parse import urlsplit

from .version import PRODUCT_SERIES

RELEASE_HOST = 'api.github.com'
RELEASE_PATH = '/repos/Adib0105/JARVIS-AI-OMEGA/releases/latest'
MAX_RELEASE_RESPONSE_BYTES = 1_000_000


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip('v')
    parts = []
    for token in clean.split('.'):
        digits = ''.join(ch for ch in token if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts or [0])


def _trusted_release_page(value: str) -> str:
    """Return only the canonical repository's HTTPS release page."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    expected_prefix = '/Adib0105/JARVIS-AI-OMEGA/releases/'
    try:
        port = parsed.port
    except ValueError:
        return ''
    if parsed.scheme != 'https' or parsed.hostname != 'github.com' or port not in {None, 443}:
        return ''
    if parsed.username or parsed.password or not parsed.path.startswith(expected_prefix):
        return ''
    return value


def check_latest_release(current_version: str, timeout: float = 8.0) -> dict:
    connection = http.client.HTTPSConnection(RELEASE_HOST, timeout=max(1.0, min(float(timeout), 30.0)))
    try:
        connection.request(
            'GET',
            RELEASE_PATH,
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': f'JARVIS-AI-OMEGA-{PRODUCT_SERIES}',
            },
        )
        response = connection.getresponse()
        if response.status == 404:
            return {'available': False, 'published': False, 'message': 'No GitHub Release has been published yet.'}
        if response.status != 200:
            raise RuntimeError(f'GitHub update check failed: HTTP {response.status}')
        raw = response.read(MAX_RELEASE_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RELEASE_RESPONSE_BYTES:
            raise RuntimeError('GitHub update response exceeded the safe size limit.')
        payload = json.loads(raw.decode('utf-8'))
        if not isinstance(payload, dict):
            raise RuntimeError('GitHub update response was not a JSON object.')
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f'GitHub update check failed: {exc}') from exc
    finally:
        connection.close()

    tag = str(payload.get('tag_name') or '').strip()
    url = _trusted_release_page(str(payload.get('html_url') or '').strip())
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
