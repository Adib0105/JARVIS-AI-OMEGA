from __future__ import annotations

import inspect
import unittest

from jarvis.core import JarvisOmega
from jarvis.runtime_guard import install_runtime_guards
from jarvis.skill_runtime_extension import install_skill_runtime


class RuntimeCompositionTests(unittest.TestCase):
    def test_runtime_guard_does_not_mutate_public_core(self):
        chat = JarvisOmega.chat
        select_model = JarvisOmega._select_model
        install_runtime_guards()
        self.assertIs(JarvisOmega.chat, chat)
        self.assertIs(JarvisOmega._select_model, select_model)

    def test_quality_behavior_is_declared_on_public_core(self):
        self.assertIn('chat', JarvisOmega.__dict__)
        self.assertIn('_select_model', JarvisOmega.__dict__)
        chat_source = inspect.getsource(JarvisOmega.chat)
        model_source = inspect.getsource(JarvisOmega._select_model)
        self.assertIn('local_identity_answer', chat_source)
        self.assertIn('clean_display_text', chat_source)
        self.assertIn('preferred_text_model', model_source)

    def test_skill_runtime_shim_does_not_mutate_public_core(self):
        methods = {
            name: getattr(JarvisOmega, name)
            for name in ('prepare_skill_build', 'run_skill_build', 'activate_skill', 'disable_skill')
        }
        install_skill_runtime()
        for name, method in methods.items():
            self.assertIs(getattr(JarvisOmega, name), method)
            self.assertIn(name, JarvisOmega.__dict__)


if __name__ == '__main__':
    unittest.main()
