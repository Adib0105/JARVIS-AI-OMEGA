import tempfile
import unittest
from pathlib import Path

from jarvis.memory import MemoryStore
from jarvis.vector_memory import cosine_sparse, hashed_vector, rank_texts


class V6VectorNotesTests(unittest.TestCase):
    def test_vector_similarity_prefers_relevant_text(self):
        rows = [
            {'content': 'Python debugging and fixing a traceback error', 'id': 1},
            {'content': 'Beach weather and tropical vacation planning', 'id': 2},
        ]
        ranked = rank_texts('debug python error', rows, limit=2)
        self.assertTrue(ranked)
        self.assertEqual(ranked[0]['id'], 1)
        self.assertGreaterEqual(cosine_sparse(hashed_vector('python error'), hashed_vector('python error fix')), 0)

    def test_notes_and_session_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'memory.db')
            note = store.add_note('Project', 'JARVIS OMEGA V6 roadmap')
            self.assertEqual(note['title'], 'Project')
            self.assertEqual(store.search_notes('OMEGA')[0]['id'], note['id'])

            sid = store.new_session('summary')
            store.set_session_summary(sid, 'User is testing V6.')
            self.assertEqual(store.get_session_summary(sid), 'User is testing V6.')
            stats = store.stats()
            self.assertEqual(stats['notes'], 1)
            self.assertEqual(stats['session_summaries'], 1)

    def test_vector_knowledge_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'knowledge.db')
            store.index_knowledge('python.md', 'Flask debugging traceback route server Python')
            store.index_knowledge('travel.md', 'Tropical beach hotel itinerary')
            rows = store.vector_search_knowledge('Python server debugging', 3)
            self.assertTrue(rows)
            self.assertEqual(rows[0]['source'], 'python.md')


if __name__ == '__main__':
    unittest.main()
