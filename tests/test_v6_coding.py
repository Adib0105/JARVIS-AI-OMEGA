import tempfile
import unittest
from pathlib import Path

from jarvis.coding_tools import CodingWorkspace
from jarvis.local_files import LocalFiles


class V6CodingTests(unittest.TestCase):
    def _workspace(self, root: Path) -> CodingWorkspace:
        files = LocalFiles()
        files.roots = (root.resolve(),)
        return CodingWorkspace(files)

    def test_write_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'demo.py'
            target.write_text('old = 1\n', encoding='utf-8')
            result = self._workspace(root).write_text(str(target), 'new = 2\n')
            self.assertEqual(target.read_text(encoding='utf-8'), 'new = 2\n')
            self.assertIsNotNone(result['backup'])
            self.assertTrue(Path(result['backup']).exists())

    def test_tree_skips_git_and_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'app.py').write_text('print(1)', encoding='utf-8')
            (root / '.git').mkdir()
            (root / '.git' / 'config').write_text('secret-ish', encoding='utf-8')
            tree = self._workspace(root).tree(str(root), 50)
            self.assertTrue(any('src' in item for item in tree))
            self.assertFalse(any('.git' in item for item in tree))

    def test_reject_binary_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(PermissionError):
                self._workspace(root).write_text(str(root / 'bad.exe'), 'x')


if __name__ == '__main__':
    unittest.main()
