import tempfile
import unittest
from pathlib import Path

from jarvis.documents import DocumentReader
from jarvis.local_files import LocalFiles


class V6DocumentTests(unittest.TestCase):
    def _reader(self, root: Path) -> DocumentReader:
        files = LocalFiles()
        files.roots = (root.resolve(),)
        return DocumentReader(files)

    def test_csv_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'data.csv'
            path.write_text('name,score\nAdib,99\n', encoding='utf-8')
            doc = self._reader(root).extract(str(path))
            self.assertEqual(doc['metadata']['type'], 'csv')
            self.assertIn('Adib', doc['text'])

    def test_text_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'notes.txt'
            path.write_text('JARVIS V6 document intelligence', encoding='utf-8')
            doc = self._reader(root).extract(str(path))
            self.assertIn('JARVIS V6', doc['text'])

    def test_reject_outside_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = Path(other) / 'x.txt'
            outside.write_text('blocked', encoding='utf-8')
            with self.assertRaises(PermissionError):
                self._reader(root).extract(str(outside))


if __name__ == '__main__':
    unittest.main()
