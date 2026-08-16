import tempfile
import unittest
from pathlib import Path

from jarvis.document_index import DocumentIndexStore
from jarvis.documents import DocumentReader
from jarvis.local_files import LocalFiles
from jarvis.memory import MemoryStore
from jarvis.tools import ToolRegistry


class AllowDecision:
    allowed = True
    reason = 'test'


class AllowAll:
    def check(self, name, args):
        return AllowDecision()


class V75DocumentIndexTests(unittest.TestCase):
    def test_reader_exposes_stable_content_hash_and_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'notes.txt'
            path.write_text('same content', encoding='utf-8')
            files = LocalFiles()
            files.roots = (root.resolve(),)
            reader = DocumentReader(files)
            first = reader.extract(str(path))
            second = reader.extract(str(path))
            self.assertEqual(first['content_sha256'], second['content_sha256'])
            self.assertEqual(len(first['content_sha256']), 64)
            self.assertIsInstance(first['mtime_ns'], int)
            path.write_text('changed content', encoding='utf-8')
            changed = reader.extract(str(path))
            self.assertNotEqual(first['content_sha256'], changed['content_sha256'])

    def test_index_registry_distinguishes_unchanged_update_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentIndexStore(Path(tmp) / 'jarvis.db')
            self.assertEqual(store.decide('a.txt', 'aaa').action, 'INDEX')
            store.record(source='a.txt', content_hash='aaa', size_bytes=1, mtime_ns=1, chunks=2, metadata={'x': 1})
            same = store.decide('a.txt', 'aaa')
            self.assertEqual(same.action, 'UNCHANGED')
            self.assertEqual(same.chunks, 2)
            update = store.decide('a.txt', 'bbb')
            self.assertEqual(update.action, 'UPDATE')
            duplicate = store.decide('copy.txt', 'aaa')
            self.assertEqual(duplicate.action, 'DUPLICATE')
            self.assertEqual(duplicate.duplicate_of, 'a.txt')

    def test_tool_document_index_skips_unchanged_and_duplicate_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / 'jarvis.db'
            original = root / 'doc.txt'
            copy = root / 'copy.txt'
            original.write_text('alpha beta gamma\n' * 200, encoding='utf-8')
            copy.write_bytes(original.read_bytes())

            memory = MemoryStore(db)
            tools = ToolRegistry(memory, permission_checker=AllowAll())
            tools.files.roots = (root.resolve(),)

            first = tools._index_document(str(original))
            second = tools._index_document(str(original))
            duplicate = tools._index_document(str(copy))

            self.assertEqual(first['index']['status'], 'indexed')
            self.assertEqual(second['index']['status'], 'unchanged')
            self.assertEqual(duplicate['index']['status'], 'duplicate')
            self.assertEqual(duplicate['index']['duplicate_of'], str(original.resolve()))

            original.write_text('delta epsilon zeta\n' * 200, encoding='utf-8')
            updated = tools._index_document(str(original))
            self.assertEqual(updated['index']['status'], 'updated')
            self.assertTrue(updated['index']['previous_hash'])


if __name__ == '__main__':
    unittest.main()
