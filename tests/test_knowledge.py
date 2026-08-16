import tempfile
import unittest
from pathlib import Path

from jarvis.memory import MemoryStore


class KnowledgeTests(unittest.TestCase):
    def test_index_and_search_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'jarvis.db')
            result = store.index_knowledge('notes.txt', 'Python decorators wrap functions. SQLite stores local data.')
            self.assertGreater(result['chunks'], 0)
            hits = store.search_knowledge('decorators', 5)
            self.assertTrue(hits)
            self.assertEqual(hits[0]['source'], 'notes.txt')

    def test_export_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'jarvis.db')
            sid = store.new_session('test')
            store.add_message(sid, 'user', 'hello')
            store.add_message(sid, 'assistant', 'hi')
            target = store.export_session(sid, Path(tmp) / 'exports')
            self.assertTrue(target.exists())
            text = target.read_text(encoding='utf-8')
            self.assertIn('hello', text)
            self.assertIn('hi', text)


if __name__ == '__main__':
    unittest.main()
