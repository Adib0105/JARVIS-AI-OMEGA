import tempfile
import unittest
from pathlib import Path

from jarvis.agent.context import ContextManager
from jarvis.memory_v7 import MemoryKind, V7MemoryStore
from jarvis.storage.migrations import SchemaMigrator


class V7MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'memory.db'
        self.memory = V7MemoryStore(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_migrates_to_v7_without_deleting_legacy_tables(self):
        migrator = SchemaMigrator(self.db)
        self.assertEqual(migrator.current_version(), 7)
        with self.memory._connect() as conn:
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertIn('messages', names)
        self.assertIn('facts', names)
        self.assertIn('v7_memories', names)
        self.assertIn('v7_document_index', names)

    def test_semantic_key_supersedes_old_value_but_preserves_current_truth(self):
        first = self.memory.remember_v7(
            'User prefers red.', kind=MemoryKind.SEMANTIC, key='favorite_color', confidence=0.7, source='conversation'
        )
        second = self.memory.remember_v7(
            'User prefers blue.', kind=MemoryKind.SEMANTIC, key='favorite_color', confidence=0.95, source='current-user'
        )
        self.assertNotEqual(first['id'], second['id'])
        results = self.memory.search_memories('favorite color blue', kinds=[MemoryKind.SEMANTIC], limit=10)
        self.assertTrue(any('blue' in row['content'].lower() for row in results))
        self.assertFalse(any('red' in row['content'].lower() for row in results))

    def test_memory_reinforcement_keeps_same_id_and_raises_confidence(self):
        first = self.memory.remember_v7('Project is V7.', key='project_version', confidence=0.5)
        second = self.memory.remember_v7('Project is V7.', key='project_version', confidence=0.9, verified=True)
        self.assertEqual(first['id'], second['id'])
        rows = self.memory.search_memories('project version V7', limit=5)
        match = next(row for row in rows if row['id'] == first['id'])
        self.assertGreaterEqual(match['confidence'], 0.9)
        self.assertIsNotNone(match['last_verified'])

    def test_working_memory_is_session_and_mission_scoped(self):
        self.memory.set_working_memory('s1', 'current_file', 'alpha.py', mission_id='m1')
        self.memory.set_working_memory('s1', 'current_file', 'beta.py', mission_id='m2')
        self.assertEqual(self.memory.get_working_memory('s1', 'm1')[0]['content'], 'alpha.py')
        self.assertEqual(self.memory.get_working_memory('s1', 'm2')[0]['content'], 'beta.py')
        self.assertEqual(self.memory.clear_working_memory('s1', 'm1'), 1)

    def test_secret_like_persistent_memory_and_indexing_are_blocked(self):
        with self.assertRaises(PermissionError):
            self.memory.remember_v7('api_key=sk-proj-abcdefghijklmnopqrstuvwxyz123456')
        with self.assertRaises(PermissionError):
            self.memory.index_knowledge('secret.txt', 'password: very-secret-password')

    def test_document_duplicate_hash_avoids_reindexing(self):
        first = self.memory.index_knowledge('notes.md', 'JARVIS verification evidence and recovery design.')
        second = self.memory.index_knowledge('notes.md', 'JARVIS verification evidence and recovery design.')
        self.assertFalse(first['duplicate_unchanged'])
        self.assertTrue(second['duplicate_unchanged'])
        self.assertEqual(first['content_hash'], second['content_hash'])

    def test_hybrid_retrieval_prioritizes_relevant_knowledge(self):
        self.memory.index_knowledge('one.md', 'The mission verifier checks tool evidence after actions.')
        self.memory.index_knowledge('two.md', 'A recipe uses tomatoes, garlic and olive oil.')
        rows = self.memory.hybrid_search_knowledge('mission tool verification evidence', 2)
        self.assertEqual(rows[0]['source'], 'one.md')
        self.assertIn('bm25_score', rows[0])
        self.assertIn('sparse_score', rows[0])
        self.assertIn('embedding_score', rows[0])

    def test_context_priority_puts_current_request_before_stale_memory(self):
        session = self.memory.new_session('context')
        self.memory.remember_v7('User prefers red.', key='color', confidence=0.9, source='old-conversation')
        self.memory.add_message(session, 'user', 'I prefer blue now. Use blue.')
        bundle = ContextManager(self.memory, max_chars=8000).build(
            session_id=session,
            current_request='I prefer blue now. Use blue.',
        )
        self.assertIn('CURRENT USER REQUEST — HIGHEST PRIORITY', bundle.text)
        self.assertLess(bundle.text.index('I prefer blue now'), bundle.text.find('User prefers red') if 'User prefers red' in bundle.text else len(bundle.text))
        self.assertIn('Current user input always overrides stale', bundle.text)


if __name__ == '__main__':
    unittest.main()
