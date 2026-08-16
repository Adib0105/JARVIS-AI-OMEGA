import tempfile
import unittest
from pathlib import Path

from PIL import Image

from jarvis.attachments import image_data_url, image_info, normalize_image_paths, validate_image


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.image_path = self.root / 'sample.png'
        Image.new('RGB', (800, 600), 'white').save(self.image_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_and_info(self):
        path = validate_image(self.image_path)
        self.assertEqual(path, self.image_path.resolve())
        info = image_info(path)
        self.assertEqual(info['width'], 800)
        self.assertEqual(info['height'], 600)

    def test_provider_data_url(self):
        url = image_data_url(self.image_path)
        self.assertTrue(url.startswith('data:image/jpeg;base64,'))

    def test_normalize_image_paths(self):
        paths = normalize_image_paths([self.image_path])
        self.assertEqual(len(paths), 1)

    def test_reject_unsupported_extension(self):
        bad = self.root / 'sample.txt'
        bad.write_text('not an image', encoding='utf-8')
        with self.assertRaises(ValueError):
            validate_image(bad)


if __name__ == '__main__':
    unittest.main()
