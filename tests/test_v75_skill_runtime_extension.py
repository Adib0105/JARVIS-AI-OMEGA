import unittest

from jarvis.core import JarvisOmega
from jarvis.skill_runtime_extension import install_skill_runtime


class V75SkillRuntimeExtensionTests(unittest.TestCase):
    def test_installer_exposes_guarded_skill_lifecycle_methods(self):
        install_skill_runtime()
        self.assertTrue(getattr(JarvisOmega, '_v75_skill_runtime_installed', False))
        for name in ('prepare_skill_build', 'run_skill_build', 'activate_skill', 'disable_skill'):
            self.assertTrue(callable(getattr(JarvisOmega, name, None)), name)


if __name__ == '__main__':
    unittest.main()
