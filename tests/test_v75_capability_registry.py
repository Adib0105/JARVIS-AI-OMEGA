import importlib.util
import unittest

from jarvis.capability_registry import CapabilityRegistry, CapabilityStatus
from jarvis.core import JarvisOmega


class V75CapabilityRegistryTests(unittest.TestCase):
    def test_registry_contains_required_runtime_capabilities(self):
        registry = CapabilityRegistry()
        snapshot = {item['name']: item for item in registry.snapshot(refresh=False)}
        required = {
            'Chat', 'Vision', 'Memory', 'Missions', 'Computer Use', 'Browser',
            'Coding', 'Documents', 'Voice', 'Microphone', 'Google Workspace',
            'Local AI', 'Self Development', 'Capability Registry',
        }
        self.assertTrue(required.issubset(snapshot))

    def test_records_expose_master_plan_metadata(self):
        item = CapabilityRegistry().get('Memory')
        self.assertIsNotNone(item)
        self.assertTrue(item.version)
        self.assertTrue(item.description)
        self.assertIsInstance(item.status, CapabilityStatus)
        self.assertIsInstance(item.dependencies, tuple)
        self.assertIsInstance(item.permissions, tuple)
        self.assertTrue(item.risk)
        self.assertIsInstance(item.tests, tuple)
        self.assertTrue(item.last_verified)
        self.assertTrue(item.implementation_path)

    def test_registry_does_not_fake_self_development(self):
        registry = CapabilityRegistry()
        item = registry.get('Self Development')
        self.assertIsNotNone(item)
        package_exists = importlib.util.find_spec('jarvis.self_development') is not None
        if package_exists:
            self.assertIn(item.status, {CapabilityStatus.EXPERIMENTAL, CapabilityStatus.AVAILABLE})
        else:
            self.assertEqual(item.status, CapabilityStatus.MISSING)

    def test_prompt_summary_marks_missing_or_disabled_truthfully(self):
        summary = CapabilityRegistry().summary_for_prompt()
        self.assertIn('Do not claim MISSING or DISABLED capabilities as working', summary)
        self.assertIn('Capability Registry: AVAILABLE', summary)

    def test_public_core_exposes_capability_status_api(self):
        self.assertTrue(callable(getattr(JarvisOmega, 'capability_status', None)))


if __name__ == '__main__':
    unittest.main()
