import tempfile
import unittest
from pathlib import Path

from jarvis.coding_agent import CodingAgentV2, CodingRun, CodingStage
from jarvis.local_files import LocalFiles


class V75CodingAgentTests(unittest.TestCase):
    def test_edit_without_explicit_approval_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = LocalFiles(); files.roots = (root.resolve(),)
            agent = CodingAgentV2(files)
            run = CodingRun(str(root), 'change x')
            result = agent.apply_reviewed_changes(
                run, {'x.py': 'VALUE=2\n'}, explicit_edit_approval=False,
            )
            self.assertEqual(result.stage, CodingStage.APPROVAL)
            self.assertFalse((root / 'x.py').exists())

    def test_project_escape_is_rejected_before_outside_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / 'project'; project.mkdir()
            files = LocalFiles(); files.roots = (root.resolve(),)
            agent = CodingAgentV2(files)
            run = CodingRun(str(project), 'unsafe escape')
            result = agent.apply_reviewed_changes(
                run, {'../outside.py': 'VALUE=2\n'}, explicit_edit_approval=True,
            )
            self.assertEqual(result.stage, CodingStage.FAILED)
            self.assertFalse((root / 'outside.py').exists())
            self.assertIn('escaped project root', result.error)


if __name__ == '__main__':
    unittest.main()
