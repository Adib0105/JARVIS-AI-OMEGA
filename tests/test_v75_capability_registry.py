import importlib.util
import json
import unittest
from pathlib import Path

from jarvis.capability_registry import CapabilityRegistry, CapabilityStatus
from jarvis.core import JarvisOmega
from jarvis.version import APP_VERSION


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
        payload = item.as_dict()
        required = {
            'name', 'version', 'status', 'implementation_path', 'entry_points',
            'dependencies', 'permissions', 'risk_level', 'tests', 'last_verified',
            'evidence', 'known_limitations',
        }
        self.assertTrue(required.issubset(payload))

    def test_all_test_evidence_paths_exist(self):
        root = Path(__file__).resolve().parents[1]
        missing = []
        for item in CapabilityRegistry().snapshot(refresh=False):
            for path in item['tests']:
                if not (root / path).is_file():
                    missing.append(f"{item['name']}: {path}")
        self.assertEqual(missing, [])

    def test_committed_inventory_matches_runtime_schema(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / 'docs' / 'capability-inventory.json').read_text(encoding='utf-8'))
        runtime = CapabilityRegistry().snapshot(refresh=False)
        required = {
            'name', 'version', 'status', 'implementation_path', 'entry_points',
            'dependencies', 'permissions', 'risk_level', 'tests', 'last_verified',
            'evidence', 'known_limitations',
        }
        self.assertEqual(payload['application_version'], APP_VERSION)
        self.assertEqual(
            {item['name'] for item in payload['capabilities']},
            {item['name'] for item in runtime},
        )
        self.assertTrue(payload['capabilities'])
        for item in payload['capabilities']:
            self.assertTrue(required.issubset(item))
            self.assertIn(item['status'], {status.value for status in CapabilityStatus})

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
