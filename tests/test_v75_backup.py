import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jarvis.storage.backup import BackupManager


class V75BackupTests(unittest.TestCase):
    @staticmethod
    def _seed(path: Path, value: str):
        conn = sqlite3.connect(str(path))
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS sample(value TEXT NOT NULL)')
            conn.execute('DELETE FROM sample')
            conn.execute('INSERT INTO sample(value) VALUES (?)', (value,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _read(path: Path):
        conn = sqlite3.connect(str(path))
        try:
            return conn.execute('SELECT value FROM sample').fetchone()[0]
        finally:
            conn.close()

    def test_backup_has_integrity_manifest_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'jarvis.db'
            self._seed(db, 'original')
            manager = BackupManager(db, root / 'backups')
            result = manager.create_backup('test')
            backup = Path(result['database'])
            manifest = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
            self.assertTrue(manager.integrity(backup)['ok'])
            self.assertEqual(manifest['database_sha256'], result['database_sha256'])
            self.assertTrue(manager.verify_backup(backup)['ok'])

    def test_restore_requires_confirmation_and_keeps_pre_restore_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'jarvis.db'
            self._seed(db, 'original')
            manager = BackupManager(db, root / 'backups')
            backup = Path(manager.create_backup('good')['database'])
            self._seed(db, 'changed')
            with self.assertRaises(PermissionError):
                manager.restore_database(backup, explicit_confirmation=False)
            result = manager.restore_database(backup, explicit_confirmation=True)
            self.assertTrue(result['ok'])
            self.assertEqual(self._read(db), 'original')
            self.assertTrue(Path(result['pre_restore_backup']['database']).exists())

    def test_export_import_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'jarvis.db'
            self._seed(db, 'portable')
            manager = BackupManager(db, root / 'backups')
            archive = Path(manager.export_data(root / 'export.zip')['archive'])
            self.assertTrue(archive.exists())
            self._seed(db, 'mutated')
            with self.assertRaises(PermissionError):
                manager.import_archive(archive, explicit_confirmation=False)
            result = manager.import_archive(archive, explicit_confirmation=True)
            self.assertTrue(result['ok'])
            self.assertEqual(self._read(db), 'portable')


if __name__ == '__main__':
    unittest.main()
