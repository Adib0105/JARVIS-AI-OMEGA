import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.memory_lifecycle import MemoryLifecycleManager
from jarvis.memory_v7 import V7MemoryStore


class V75MemoryLifecycleTests(unittest.TestCase):
    @staticmethod
    def _seed(path: Path):
        conn = sqlite3.connect(str(path))
        try:
            conn.execute('''CREATE TABLE v7_memories (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                stable_key TEXT,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                updated_at TEXT NOT NULL,
                last_verified TEXT,
                status TEXT NOT NULL
            )''')
            old = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
            conn.executemany(
                'INSERT INTO v7_memories VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                [
                    ('M1', 'SEMANTIC', 'favorite_color', 'blue', 0.70, old, old, 'ACTIVE'),
                    ('M2', 'SEMANTIC', 'favorite_color', 'green', 0.80, old, old, 'ACTIVE'),
                    ('M3', 'EPISODIC', None, 'did a task', 0.60, old, old, 'ACTIVE'),
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def test_actual_v7_store_schema_is_lifecycle_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jarvis.db'
            V7MemoryStore(path)
            manager = MemoryLifecycleManager(path)
            columns = manager._require_schema()
            self.assertTrue({'id', 'content', 'confidence', 'updated_at', 'status'}.issubset(columns))

    def test_contradiction_reinforce_supersede_and_decay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jarvis.db'
            self._seed(path)
            manager = MemoryLifecycleManager(path)
            contradictions = manager.contradictions()
            self.assertEqual(len(contradictions), 1)
            self.assertEqual(contradictions[0].stable_key, 'favorite_color')

            reinforced = manager.reinforce('M2', amount=0.1)
            self.assertAlmostEqual(reinforced['confidence'], 0.9)

            relation = manager.supersede('M1', 'M2', reason='newer verified preference')
            self.assertEqual(relation['status'], 'SUPERSEDED')
            self.assertTrue(manager.relations('M1'))

            decay = manager.decay_stale(older_than_days=90, decay=0.6, stale_below=0.35)
            self.assertGreaterEqual(decay['updated'], 1)
            conn = sqlite3.connect(str(path))
            try:
                status = conn.execute("SELECT status FROM v7_memories WHERE id='M2'").fetchone()[0]
                episodic = conn.execute("SELECT confidence FROM v7_memories WHERE id='M3'").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(status, 'STALE')
            self.assertEqual(episodic, 0.6)  # default decay targets semantic memory only


if __name__ == '__main__':
    unittest.main()
