import tempfile
import unittest
from pathlib import Path

from jarvis.v10_group_a import AwarenessMode, GROUP_A_FEATURES, GroupAController


class GroupATests(unittest.TestCase):
    def test_exactly_25_features(self):
        self.assertEqual(len(GROUP_A_FEATURES), 25)
        self.assertEqual([f.number for f in GROUP_A_FEATURES], list(range(1, 26)))

    def test_manifest_and_readiness_are_complete(self):
        ctl = GroupAController()
        self.assertEqual(len(ctl.feature_manifest()), 25)
        self.assertEqual(ctl.readiness()['total'], 25)
        self.assertEqual(ctl.feature_status(1)['key'], 'live_companion')
        self.assertIsNone(ctl.feature_status(99))

    def test_awareness_off_rejects_context(self):
        ctl = GroupAController()
        self.assertFalse(ctl.update_context(app='Chrome', resource='page'))
        self.assertEqual(ctl.context_snapshot(), {'app': None, 'resource': None, 'monitor': None})

    def test_context_reference(self):
        ctl = GroupAController()
        ctl.set_awareness(AwarenessMode.ON_DEMAND)
        self.assertTrue(ctl.update_context(app='VS Code', resource='C:/work/app.py', monitor=1))
        self.assertEqual(ctl.resolve_context_reference('isko'), 'C:/work/app.py')
        self.assertEqual(ctl.resolve_context_reference('wahi file'), 'C:/work/app.py')
        self.assertEqual(ctl.resolve_context_reference('current app'), 'VS Code')
        self.assertEqual(ctl.context_snapshot()['monitor'], 1)

    def test_runtime_toggles(self):
        ctl = GroupAController()
        ctl.set_wake_word(True)
        ctl.set_startup(True)
        ctl.set_background(True)
        ctl.set_tray(False)
        self.assertTrue(ctl.state.wake_word_enabled)
        self.assertTrue(ctl.state.startup_enabled)
        self.assertTrue(ctl.state.background_enabled)
        self.assertFalse(ctl.state.tray_enabled)

    def test_routine_learning_listing_and_forgetting(self):
        ctl = GroupAController()
        ctl.learn_routine('morning', ['open mail', 'show calendar'])
        routines = ctl.list_routines()
        self.assertEqual(routines['morning'], ['open mail', 'show calendar'])
        routines['morning'].append('mutated copy')
        self.assertEqual(len(ctl.state.learned_routines['morning']), 2)
        self.assertTrue(ctl.forget_routine('morning'))

    def test_invalid_routine_is_rejected(self):
        ctl = GroupAController()
        with self.assertRaises(ValueError):
            ctl.learn_routine('', [])

    def test_file_target_is_root_scoped(self):
        ctl = GroupAController()
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            inside = str(Path(root) / 'notes.txt')
            outside = str(Path(other) / 'secret.txt')
            self.assertIsNotNone(ctl.safe_file_target(inside, [root]))
            self.assertIsNone(ctl.safe_file_target(outside, [root]))


if __name__ == '__main__':
    unittest.main()
