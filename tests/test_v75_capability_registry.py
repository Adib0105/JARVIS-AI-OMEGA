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

    def test_records_expose_master_plan_metadata_without_fake_verification(self):
        item = CapabilityRegistry().get('Memory')
        self.assertIsNotNone(item)
        self.assertTrue(item.version)
        self.assertTrue(item.description)
        self.assertIsInstance(item.status, CapabilityStatus)
        self.assertIsInstance(item.dependencies, tuple)
        self.assertIsInstance(item.permissions, tuple)
        self.assertTrue(item.risk)
        self.assertEqual(item.risk_level, item.risk)
        self.assertIsInstance(item.tests, tuple)
        self.assertIsNone(item.last_verified)
        self.assertIsNone(item.last_verified_at)
        self.assertTrue(item.test_status)
        self.assertIsNone(item.success_rate)
        self.assertIsNone(item.failure_rate)
        self.assertTrue(item.implementation_path)

    def test_registry_refresh_never_invents_verification_timestamp(self):
        registry = CapabilityRegistry()
        first = {item['name']: item for item in registry.snapshot(refresh=False)}
        second = {item['name']: item for item in registry.snapshot(refresh=True)}
        for name in first:
            self.assertIsNone(first[name]['last_verified_at'], name)
            self.assertIsNone(second[name]['last_verified_at'], name)

    def test_external_or_physical_capabilities_are_not_verified_by_presence(self):
        snapshot = {item['name']: item for item in CapabilityRegistry().snapshot(refresh=False)}
        for name in ('Chat', 'Vision', 'Browser', 'Voice', 'Microphone'):
            item = snapshot[name]
            if item['status'] not in {'DISABLED', 'MISSING', 'DEGRADED', 'BROKEN'}:
                self.assertEqual(item['status'], 'NOT_VERIFIED', name)

    def test_registry_does_not_fake_self_development(self):
        registry = CapabilityRegistry()
        item = registry.get('Self Development')
        self.assertIsNotNone(item)
        package_exists = importlib.util.find_spec('jarvis.self_development') is not None
        if package_exists:
            self.assertIn(item.status, {CapabilityStatus.EXPERIMENTAL, CapabilityStatus.AVAILABLE})
        else:
            self.assertEqual(item.status, CapabilityStatus.MISSING)

    def test_prompt_summary_marks_unverified_or_unavailable_truthfully(self):
        summary = CapabilityRegistry().summary_for_prompt()
        self.assertIn('Do not claim NOT_VERIFIED, MISSING, DISABLED, DEGRADED, or BROKEN capabilities as verified working', summary)
        self.assertIn('Capability Registry: AVAILABLE', summary)

    def test_public_core_exposes_capability_status_api(self):
        self.assertTrue(callable(getattr(JarvisOmega, 'capability_status', None)))


if __name__ == '__main__':
    unittest.main()
