import os
import tempfile
import unittest
from pathlib import Path


# unittest discovers modules lexicographically. Self-development/release tests spawn
# fresh Python subprocesses in temporary Git repositories that intentionally contain
# only the files under test, not this project's .gitignore. Redirect child-process
# bytecode caches outside those repositories so their Git diff matches the real JARVIS
# invariant where __pycache__/ and *.pyc are ignored.
_CACHE_ROOT = Path(tempfile.gettempdir()) / 'jarvis-v75-test-pycache'
_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ['PYTHONPYCACHEPREFIX'] = str(_CACHE_ROOT)


class TestEnvironmentContract(unittest.TestCase):
    def test_child_python_cache_prefix_is_outside_repo_temp_worktrees(self):
        self.assertEqual(os.environ.get('PYTHONPYCACHEPREFIX'), str(_CACHE_ROOT))
        self.assertTrue(_CACHE_ROOT.is_absolute())


if __name__ == '__main__':
    unittest.main()
