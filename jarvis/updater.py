from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .version import APP_VERSION

RELEASE_API = 'https://api.github.com/repos/Adib0105/JARVIS-AI-OMEGA/releases/latest'
INSTALLER_PREFIX = 'JARVIS-AI-OMEGA-Setup-'
MAX_INSTALLER_BYTES = 500 * 1024 * 1024


def _parse_version(value: str) -> Version:
    clean = str(value or '').strip()
    if clean.lower().startswith('v'):
        clean = clean[1:]
    try:
        return Version(clean)
    except InvalidVersion as exc:
        raise ValueError(f'Unsupported release version: {value!r}') from exc


def _release_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': f'JARVIS-AI-OMEGA/{APP_VERSION}'})


def check_latest_release(current_version: str, timeout: float = 8.0) -> dict:
    try:
        with urllib.request.urlopen(_release_request(RELEASE_API), timeout=timeout) as response:
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
    installer = None
    checksum = None
    for asset in payload.get('assets') or []:
        name = str(asset.get('name') or '')
        download_url = str(asset.get('browser_download_url') or '')
        if name.startswith(INSTALLER_PREFIX) and name.lower().endswith('.exe') and download_url:
            installer = {'name': name, 'url': download_url, 'size': int(asset.get('size') or 0)}
        elif name.upper() == 'SHA256.TXT' and download_url:
            checksum = {'name': name, 'url': download_url}
    return {'available': newer, 'published': True, 'current_version': current_version, 'latest_version': tag, 'url': url, 'name': payload.get('name') or tag, 'installer': installer, 'checksum': checksum, 'message': f'New version {tag} available.' if newer else f'You are up to date ({current_version}).'}


def _download(url: str, destination: Path, *, timeout: float = 60.0, max_bytes: int = MAX_INSTALLER_BYTES) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with urllib.request.urlopen(_release_request(url), timeout=timeout) as response, destination.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError('Update download exceeded the maximum allowed size.')
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _expected_sha256(checksum_text: str, installer_name: str) -> str:
    target = installer_name.lower()
    for raw_line in checksum_text.splitlines():
        parts = raw_line.strip().replace('*', ' ').split()
        if len(parts) >= 2 and parts[1].lower() == target:
            digest = parts[0].lower()
            if len(digest) == 64 and all(ch in '0123456789abcdef' for ch in digest):
                return digest
    raise RuntimeError(f'Checksum for {installer_name} was not found in SHA256.txt.')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(release: dict, *, timeout: float = 60.0) -> Path:
    installer = release.get('installer') or {}
    checksum = release.get('checksum') or {}
    name = str(installer.get('name') or '')
    url = str(installer.get('url') or '')
    checksum_url = str(checksum.get('url') or '')
    if not name.startswith(INSTALLER_PREFIX) or not name.lower().endswith('.exe') or not url:
        raise RuntimeError('This release does not contain a supported JARVIS installer asset.')
    if not checksum_url:
        raise RuntimeError('This release has no SHA256.txt. Update refused for safety.')
    declared_size = int(installer.get('size') or 0)
    if declared_size <= 0 or declared_size > MAX_INSTALLER_BYTES:
        raise RuntimeError('Installer asset size is invalid or exceeds the update safety limit.')
    update_dir = Path(tempfile.gettempdir()) / 'JARVIS-AI-OMEGA' / 'updates'
    update_dir.mkdir(parents=True, exist_ok=True)
    installer_path = update_dir / name
    checksum_path = update_dir / 'SHA256.txt'
    _download(url, installer_path, timeout=timeout)
    _download(checksum_url, checksum_path, timeout=timeout, max_bytes=1024 * 1024)
    if installer_path.stat().st_size != declared_size:
        installer_path.unlink(missing_ok=True)
        raise RuntimeError('Downloaded installer size does not match the GitHub release asset.')
    expected = _expected_sha256(checksum_path.read_text(encoding='utf-8', errors='replace'), name)
    actual = _sha256(installer_path)
    if actual.lower() != expected.lower():
        installer_path.unlink(missing_ok=True)
        raise RuntimeError('Downloaded installer checksum verification failed. Update refused.')
    return installer_path


def launch_update(installer_path: Path) -> None:
    path = Path(installer_path).resolve()
    if os.name != 'nt':
        raise RuntimeError('Automatic installer updates are supported on Windows only.')
    if not path.is_file() or not path.name.startswith(INSTALLER_PREFIX) or path.suffix.lower() != '.exe':
        raise RuntimeError('Verified JARVIS installer is missing.')
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen([str(path), '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)


__all__ = ['check_latest_release', 'download_update', 'launch_update']
