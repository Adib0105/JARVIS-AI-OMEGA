import tempfile
import unittest
from pathlib import Path

from jarvis.v10_group_a import AwarenessMode, GROUP_A_FEATURES, GroupAController


class GroupATests(unittest.TestCase):
    def test_exactly_25_features(self):
        self.assertEqual(len(GROUP_A_FEATURES), 25)
        self.assertEqual([f.number for f in GROUP_A_FEATURES], list(range(1, 26)))

    def test_awareness_off_rejects_context(self):
        ctl = GroupAController()
        self.assertFalse(ctl.update_context(app='Chrome', resource='page'))

    def test_context_reference(self):
        ctl = GroupAController()
        ctl.set_awareness(AwarenessMode.ON_DEMAND)
        self.assertTrue(ctl.update_context(app='VS Code', resource='C:/work/app.py', monitor=1))
        self.assertEqual(ctl.resolve_context_reference('isko'), 'C:/work/app.py')
        self.assertEqual(ctl.resolve_context_reference('current app'), 'VS Code')

    def test_routine_learning_and_forgetting(self):
        ctl = GroupAController()
        ctl.learn_routine('morning', ['open mail', 'show calendar'])
        self.assertEqual(len(ctl.state.learned_routines['morning']), 2)
        self.assertTrue(ctl.forget_routine('morning'))

    def test_file_target_is_root_scoped(self):
        ctl = GroupAController()
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            inside = str(Path(root) / 'notes.txt')
            outside = str(Path(other) / 'secret.txt')
            self.assertIsNotNone(ctl.safe_file_target(inside, [root]))
            self.assertIsNone(ctl.safe_file_target(outside, [root]))


if __name__ == '__main__':
    unittest.main()
