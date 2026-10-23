"""Verify the actual WG Deck vector assets shipped by the public product.

The early WGM UI wireframe was a development-only mock and is not distributed.
These tests validate the canonical Concept 09 brand files used by the Qt app.
"""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "wg_deck" / "assets" / "brand"
PRODUCT_ASSETS = (
    "wg-deck-logo-dark.svg",
    "wg-deck-logo-light.svg",
    "wg-deck-symbol-dark.svg",
    "wg-deck-symbol-light.svg",
    "wg-deck-app.svg",
)
ATTRIBUTION_ASSETS = ("matt88-logo-dark.svg", "matt88-logo-light.svg")


class CanonicalVectorTests(unittest.TestCase):
    def test_packaged_svg_files_have_safe_vector_structure(self):
        for filename in (*PRODUCT_ASSETS, *ATTRIBUTION_ASSETS):
            with self.subTest(asset=filename):
                asset = ASSETS / filename
                self.assertTrue(asset.is_file(), filename)
                root = ET.parse(asset).getroot()
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIn("viewBox", root.attrib)
                tags = {node.tag.rsplit("}", 1)[-1] for node in root.iter()}
                self.assertTrue("path" in tags or "rect" in tags)
                for forbidden in ("image", "script", "foreignObject"):
                    self.assertNotIn(forbidden, tags)
                self.assertFalse(any(
                    name.rsplit("}", 1)[-1] == "href"
                    for node in root.iter() for name in node.attrib
                ), "Packaged SVG must not reference external resources")

    def test_qt_svg_renderer_accepts_all_packaged_assets(self):
        # Render the real packaged assets, not the obsolete non-distributed
        # UI wireframe. The subprocess isolates QGuiApplication state.
        program = r"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path.cwd() / "src" / "wg_deck" / "assets" / "brand"
names = (
    "wg-deck-logo-dark.svg", "wg-deck-logo-light.svg",
    "wg-deck-symbol-dark.svg", "wg-deck-symbol-light.svg",
    "wg-deck-app.svg", "matt88-logo-dark.svg", "matt88-logo-light.svg",
)
app = QGuiApplication([])
for name in names:
    renderer = QSvgRenderer(str(root / name))
    assert renderer.isValid(), f"Qt rejected {name}"
    img = QImage(360, 160, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    assert not img.isNull(), f"Qt returned an invalid canvas for {name}"
print(f"Rendered {len(names)} bundled SVGs in Qt offscreen")
"""
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run(
            [sys.executable, "-c", program], cwd=ROOT,
            env=env, capture_output=True, text=True,
            timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
