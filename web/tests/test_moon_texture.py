"""The 4K and 8K Moon colour maps of the globe (web/viewer/vendor/moon/HD_TEXTURES.md).

Done when: the sharper maps are the recorded files (SHA-256 as written in HD_TEXTURES.md, with
source, retrieval time and credit there and in CREDITS.md); the globe shows the 2K map first and
then the sharpest copy the device should load, 8K only on a desktop; the 2K map stays the
fallback, so the globe works if a larger file fails to load.

Run from the repository root:  python -I -m unittest discover -s web/tests -t web
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
MOON = WEB / "viewer" / "vendor" / "moon"
GLOBE = WEB / "viewer" / "js" / "globe.js"


class HdMoonTextureTests(unittest.TestCase):
    def setUp(self):
        self.record = (MOON / "HD_TEXTURES.md").read_text(encoding="utf-8")
        self.globe = GLOBE.read_text(encoding="utf-8")

    def test_files_are_the_recorded_ones(self):
        for name, width in (("lroc_color_4k.jpg", 4096), ("lroc_color_8k.jpg", 8192)):
            data = (MOON / name).read_bytes()
            self.assertIn(hashlib.sha256(data).hexdigest(), self.record, name)
            self.assertEqual(data[:2], b"\xff\xd8", name)  # JPEG
            # Width from the JPEG frame header (SOF0 or SOF2), to catch a wrong file under the name.
            sof = re.search(rb"\xff[\xc0\xc2]..\x08(..)(..)", data, re.S)
            self.assertEqual((int.from_bytes(sof.group(2), "big"), int.from_bytes(sof.group(1), "big")), (width, width // 2), name)

    def test_source_and_credit_are_recorded(self):
        self.assertIn("https://svs.gsfc.nasa.gov/4720/", self.record)
        self.assertIn("lroc_color_16bit_srgb_4k.tif", self.record)
        self.assertIn("lroc_color_16bit_srgb_8k.tif", self.record)
        self.assertIn("NASA's Scientific Visualization Studio", self.record)
        credits = (WEB.parent / "CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("lroc_color_4k.jpg", credits)
        self.assertIn("lroc_color_8k.jpg", credits)

    def test_globe_loads_the_2k_map_first_and_8k_only_on_a_desktop(self):
        self.assertIn('"../vendor/moon/lroc_color_2k.jpg"', self.globe)
        self.assertIn('"../vendor/moon/lroc_color_4k.jpg"', self.globe)
        self.assertIn('"../vendor/moon/lroc_color_8k.jpg"', self.globe)
        self.assertRegex(self.globe, r'lroc_color_8k\.jpg".*width: 8192, desktopOnly: true')
        self.assertRegex(self.globe, r'lroc_color_4k\.jpg".*width: 4096, desktopOnly: false')
        # The sharper map replaces the 2K one only once it has loaded.
        self.assertLess(self.globe.index("new THREE.TextureLoader().load(TEXTURE"), self.globe.index("new THREE.TextureLoader().load(hd.url"))
        self.assertIn("t.width <= maxTextureSize", self.globe)


if __name__ == "__main__":
    unittest.main()
