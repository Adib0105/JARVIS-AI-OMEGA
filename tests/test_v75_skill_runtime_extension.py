import unittest

from jarvis.core import JarvisOmega
from jarvis.skill_runtime_extension import install_skill_runtime


class V75SkillRuntimeExtensionTests(unittest.TestCase):
    def test_compatibility_installer_is_noop_and_methods_are_native(self):
        before = {
            name: getattr(JarvisOmega, name)
            for name in ('prepare_skill_build', 'run_skill_build', 'activate_skill', 'disable_skill')
        }
        install_skill_runtime()
        for name, method in before.items():
            self.assertIs(getattr(JarvisOmega, name), method)
            self.assertIn(name, JarvisOmega.__dict__)


if __name__ == '__main__':
    unittest.main()
