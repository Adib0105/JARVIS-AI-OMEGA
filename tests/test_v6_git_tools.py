import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis.git_tools import GitWorkspace
from jarvis.local_files import LocalFiles


@unittest.skipUnless(shutil.which('git'), 'git executable not available')
class V6GitToolsTests(unittest.TestCase):
    def test_status_and_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init'], cwd=root, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=root, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=root, check=True)
            file = root / 'demo.py'
            file.write_text('value = 1\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'demo.py'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m', 'initial'], cwd=root, check=True, capture_output=True)
            file.write_text('value = 2\n', encoding='utf-8')

            files = LocalFiles()
            files.roots = (root.resolve(),)
            git = GitWorkspace(files)
            status = git.status(str(root))
            self.assertIn('demo.py', status['status'])
            diff = git.diff(str(root))
            self.assertIn('value = 2', diff['diff'])
            log = git.log(str(root), 5)
            self.assertIn('initial', log['log'])


if __name__ == '__main__':
    unittest.main()
