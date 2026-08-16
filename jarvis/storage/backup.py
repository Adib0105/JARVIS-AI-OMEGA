from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from .migrations import SchemaMigrator
from .sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S-%f')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class BackupManifest:
    created_at: str
    schema_version: int
    database_sha256: str
    database_size: int
    source_name: str
    format_version: int = 1

    def as_dict(self) -> dict:
        return asdict(self)


class BackupManager:
    """Consistent SQLite backup/export/import with integrity checks and no secrets."""

    def __init__(self, db_path: Path | None = None, backup_dir: Path | None = None) -> None:
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path(backup_dir or (self.db_path.parent / 'backups'))
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def integrity(path: Path) -> dict:
        path = Path(path)
        if not path.exists():
            return {'ok': False, 'result': 'missing', 'path': str(path)}
        try:
            conn = sqlite3.connect(str(path), timeout=10)
            try:
                result = conn.execute('PRAGMA quick_check').fetchone()[0]
            finally:
                conn.close()
            return {'ok': result == 'ok', 'result': result, 'path': str(path)}
        except Exception as exc:
            return {'ok': False, 'result': f'{type(exc).__name__}: {exc}', 'path': str(path)}

    def integrity_check(self) -> dict:
        """Check the active JARVIS database; convenient for health/self-check UIs."""
        return self.integrity(self.db_path)

    def _sqlite_backup(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with connect_sqlite(self.db_path, timeout=10) as source:
            target = sqlite3.connect(str(destination), timeout=10)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()

    def create_backup(self, label: str = 'manual') -> dict:
        safe_label = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in str(label))[:40] or 'manual'
        target = self.backup_dir / f'jarvis-{safe_label}-{_stamp()}.db'
        self._sqlite_backup(target)
        check = self.integrity(target)
        if not check['ok']:
            target.unlink(missing_ok=True)
            raise RuntimeError(f'Backup integrity check failed: {check["result"]}')
        manifest = BackupManifest(
            created_at=_now(),
            schema_version=SchemaMigrator(target).current_version(),
            database_sha256=_sha256(target),
            database_size=target.stat().st_size,
            source_name=self.db_path.name,
        )
        manifest_path = target.with_suffix(target.suffix + '.manifest.json')
        manifest_path.write_text(json.dumps(manifest.as_dict(), indent=2), encoding='utf-8')
        return {'database': str(target), 'manifest': str(manifest_path), **manifest.as_dict()}

    def verify_backup(self, backup_path: str | Path) -> dict:
        path = Path(backup_path).expanduser().resolve()
        check = self.integrity(path)
        manifest_path = path.with_suffix(path.suffix + '.manifest.json')
        manifest = None
        hash_match = None
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                hash_match = manifest.get('database_sha256') == _sha256(path)
            except Exception:
                hash_match = False
        return {
            'ok': bool(check['ok'] and (hash_match is not False)),
            'integrity': check,
            'manifest_present': manifest is not None,
            'hash_match': hash_match,
            'manifest': manifest,
        }

    def export_data(self, destination: str | Path | None = None) -> dict:
        backup = self.create_backup('export')
        db = Path(backup['database'])
        manifest = Path(backup['manifest'])
        target = Path(destination).expanduser() if destination else settings.export_dir / f'jarvis-data-{_stamp()}.zip'
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db, arcname='jarvis.db')
            archive.write(manifest, arcname='manifest.json')
        return {'archive': str(target), 'sha256': _sha256(target), 'database_backup': str(db)}

    @staticmethod
    def _safe_archive_members(archive: zipfile.ZipFile) -> set[str]:
        names = set(archive.namelist())
        for name in names:
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Backup archive contains an unsafe path.')
        return names

    def import_archive(self, archive_path: str | Path, *, explicit_confirmation: bool) -> dict:
        if not explicit_confirmation:
            raise PermissionError('Explicit confirmation is required before destructive data restore.')
        archive_path = Path(archive_path).expanduser().resolve()
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            with zipfile.ZipFile(archive_path, 'r') as archive:
                names = self._safe_archive_members(archive)
                if 'jarvis.db' not in names:
                    raise ValueError('Backup archive does not contain jarvis.db.')
                archive.extract('jarvis.db', temp)
                if 'manifest.json' in names:
                    archive.extract('manifest.json', temp)
            candidate = temp / 'jarvis.db'
            check = self.integrity(candidate)
            if not check['ok']:
                raise RuntimeError(f'Imported database failed integrity check: {check["result"]}')
            return self.restore_database(candidate, explicit_confirmation=True)

    def restore_database(self, backup_path: str | Path, *, explicit_confirmation: bool) -> dict:
        if not explicit_confirmation:
            raise PermissionError('Explicit confirmation is required before destructive database restore.')
        backup_path = Path(backup_path).expanduser().resolve()
        verification = self.verify_backup(backup_path)
        if not verification['integrity']['ok']:
            raise RuntimeError('Restore source failed SQLite integrity check.')
        pre_restore = self.create_backup('pre-restore') if self.db_path.exists() else None

        source = sqlite3.connect(str(backup_path), timeout=10)
        try:
            with connect_sqlite(self.db_path, timeout=10) as target:
                source.backup(target)
                target.commit()
        finally:
            source.close()

        final_check = self.integrity(self.db_path)
        if not final_check['ok']:
            raise RuntimeError(
                f'Restored database failed integrity check. Pre-restore backup retained at: '
                f'{pre_restore["database"] if pre_restore else "N/A"}'
            )
        return {
            'ok': True,
            'restored_from': str(backup_path),
            'pre_restore_backup': pre_restore,
            'integrity': final_check,
        }
