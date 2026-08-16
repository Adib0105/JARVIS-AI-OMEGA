import tempfile
import unittest
from pathlib import Path

from jarvis.memory import MemoryStore


class MemoryTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            mem = MemoryStore(Path(td) / 'test.db')
            sid = mem.new_session('test')
            mem.add_message(sid, 'user', 'hello')
            self.assertEqual(mem.recent_messages(sid), [('user', 'hello')])
            mem.remember('favorite editor is VS Code')
            self.assertIn('favorite editor is VS Code', mem.recall('VS Code'))


if __name__ == '__main__':
    unittest.main()
