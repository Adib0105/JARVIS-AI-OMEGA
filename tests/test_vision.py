import tempfile
import unittest
from pathlib import Path

from PIL import Image

from jarvis.vision import image_data_url


class VisionTests(unittest.TestCase):
    def test_png_is_compressed_to_provider_jpeg_data_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'screen.png'
            Image.new('RGB', (8, 8), 'white').save(path)
            data = image_data_url(path)
            self.assertTrue(data.startswith('data:image/jpeg;base64,'))

    def test_rejects_non_image_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.txt'
            path.write_text('not an image', encoding='utf-8')
            with self.assertRaises(ValueError):
                image_data_url(path)


if __name__ == '__main__':
    unittest.main()
