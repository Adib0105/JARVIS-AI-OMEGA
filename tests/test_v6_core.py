import unittest

from jarvis.core import JarvisOmega


class V6CoreTests(unittest.TestCase):
    def test_extract_json_plan(self):
        raw = '["Inspect project", "Run tests", "Review result"]'
        self.assertEqual(
            JarvisOmega._extract_plan(raw, 5),
            ['Inspect project', 'Run tests', 'Review result'],
        )

    def test_extract_bullet_plan_and_limit(self):
        raw = '1. First\n2. Second\n3. Third'
        self.assertEqual(JarvisOmega._extract_plan(raw, 2), ['First', 'Second'])


if __name__ == '__main__':
    unittest.main()
