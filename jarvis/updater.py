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
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'JARVIS-AI-OMEGA'},
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
        'asset': next((a for a in payload.get('assets', []) if a.get('name') == INSTALLER_NAME), None),
        'message': f'New version {tag} available.' if newer else f'You are up to date ({current_version}).',
    }


INSTALLER_NAME = 'JARVIS-AI-OMEGA-V7-Setup.exe'
MAX_DOWNLOAD = 600 * 1024 * 1024


def validate_asset(asset):
    import re
    from urllib.parse import urlparse
    url = str(asset.get('browser_download_url', ''))
    parsed = urlparse(url)
    digest = str(asset.get('digest', ''))
    size = asset.get('size')
    if (asset.get('name') != INSTALLER_NAME or parsed.scheme != 'https'
            or parsed.netloc != 'github.com' or parsed.query or parsed.fragment
            or not parsed.path.startswith('/Adib0105/JARVIS-AI-OMEGA/releases/download/')
            or not parsed.path.endswith('/' + INSTALLER_NAME)
            or not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest)
            or not isinstance(size, int) or not 0 < size <= MAX_DOWNLOAD):
        raise ValueError('Release has no valid verified Windows installer. Nothing was installed.')
    return url, digest.split(':', 1)[1].lower(), size


def download_installer(asset, progress=lambda done, total: None):
    import hashlib
    from pathlib import Path
    import tempfile
    import time
    url, expected, size = validate_asset(asset)
    folder = Path(tempfile.mkdtemp(prefix='jarvis-update-'))
    target = folder / INSTALLER_NAME
    started = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'JARVIS-Update'})
        with urllib.request.urlopen(request, timeout=20) as response, target.open('wb') as out:
            digest, total = hashlib.sha256(), 0
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > size or time.monotonic() - started > 600:
                    raise RuntimeError('Update download exceeded its expected size or time limit.')
                out.write(chunk)
                digest.update(chunk)
                progress(total, size)
        if total != size or digest.hexdigest() != expected:
            raise RuntimeError('Update checksum or size mismatch. Nothing was installed; retry download.')
        return target
    except Exception:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise


def start_installer_update(installer, asset):
    """Stage helper outside the app; it waits for graceful exit before replacing files."""
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    from .config import ROOT
    from .windows_integration import powershell_path
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Install the Windows Setup build first to use in-app updates.')
    _, digest, _ = validate_asset(asset)
    installer = Path(installer).resolve()
    helper = installer.parent / 'apply-update.ps1'
    shutil.copy2(ROOT / 'apply-update.ps1', helper)
    process = subprocess.Popen([powershell_path(), '-NoProfile', '-NonInteractive', '-File', str(helper),
        '-Installer', str(installer), '-AppDir', str(ROOT), '-ParentId', str(os.getpid()), '-Sha256', digest],
        cwd=str(installer.parent), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    try:
        code = process.wait(timeout=0.4)
    except subprocess.TimeoutExpired:
        return
    raise RuntimeError(f'Windows could not start the update helper (exit {code}). JARVIS stays open.')
