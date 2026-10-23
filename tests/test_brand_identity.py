"""Public product identity contract for all UI and system interfaces.

The pre-release-to-public technical rename requires a user-driven upgrade.
"""
from __future__ import annotations

from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class BrandIdentityTests(unittest.TestCase):
    def test_no_previous_brand_in_product_facing_sources(self):
        visible = [
            "src/wg_deck/ui/window.py",
            "src/wg_deck/qt_app.py",
            "privileged/org.matt88.wgdeck.policy",
            "privileged/org.matt88.wgdeck.connection.policy",
            "privileged/org.matt88.wgdeck.read.policy",
            "privileged/wg-deck-inventory.service",
            "privileged/wg-deck-inventory.timer",
            "scripts/install_desktop.sh",
            "scripts/capture_ui.py",
        ]
        for relative in visible:
            with self.subTest(file=relative):
                data = (ROOT / relative).read_text("utf-8")
                self.assertNotIn("WG " + "Quick Manager", data)

    def test_sidebar_is_only_full_brand_placement(self):
        src = (ROOT / "src/wg_deck/ui/window.py").read_text("utf-8")
        self.assertIn('self.sidebar_matt88_logo, 0, Qt.AlignmentFlag.AlignHCenter', src)
        self.assertIn('self.sidebar_matt88_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)', src)
        self.assertIn('brand.addWidget(self.wgdeck_header_logo)', src)
        self.assertIn('wg_deck_logo_pixmap(effective, width=184, height=38)', src)
        self.assertIn('(76, 20) if narrow else (86, 22)', src)
        self.assertNotIn('named_label("⬟", "brandIcon")', src)
        self.assertIn('self.menu.addAction("WG Deck")', src)
        self.assertIn('setWindowTitle("WG Deck")', src)
        self.assertIn('f"WG Deck v{__version__}"', src)
        self.assertNotIn("by matt88.it", src)
        self.assertNotIn('about_form.addWidget(', src)
        self.assertNotIn('About WG Deck", "sectionTitle"', src)

    def test_public_product_technical_identifiers(self):
        # Public WG Deck IDs are canonical; old pre-release IDs require explicit upgrade.
        install = (ROOT / "scripts/install_helper.sh").read_text("utf-8")
        self.assertIn("/usr/local/libexec/wg-deck-helper", install)
        self.assertIn("org.matt88.wgdeck.policy", install)
        login = (ROOT / "src/wg_deck/core/autostart.py").read_text("utf-8")
        self.assertIn('DESKTOP_FILE = "org.matt88.wg-deck.desktop"', login)
        self.assertNotIn("def _legacy_entry(", login)

    def test_official_logo_svg_sources_are_identified(self):
        branding = (ROOT / "src/wg_deck/ui/branding.py").read_text("utf-8")
        self.assertIn("matt88-logo-{variant}.svg", branding)
        self.assertIn("wg-deck-logo-{variant}.svg", branding)
        self.assertIn("wg-deck-app.svg", (ROOT / "src/wg_deck/qt_icon.py").read_text("utf-8"))
        for theme in ("light", "dark"):
            path = ROOT / "src" / "wg_deck" / "assets" / "brand" / f"matt88-logo-{theme}.svg"
            self.assertTrue(path.is_file())
            self.assertIn("<svg", path.read_text("utf-8"))
            app_logo = ROOT / "src" / "wg_deck" / "assets" / "brand" / f"wg-deck-logo-{theme}.svg"
            data = app_logo.read_text("utf-8")
            self.assertIn("<svg", data)
            self.assertIn("<path", data)
            self.assertNotIn("<text", data)  # wordmark is outlined paths, not external fonts
        brand_dir = ROOT / "src" / "wg_deck" / "assets" / "brand"
        for filename in (
            "wg-deck-logo-dark.svg", "wg-deck-logo-light.svg",
            "wg-deck-symbol-dark.svg", "wg-deck-symbol-light.svg",
            "wg-deck-app.svg",
        ):
            with self.subTest(svg=filename):
                data = (brand_dir / filename).read_text("utf-8")
                svg = ET.fromstring(data)
                self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIn("viewBox", svg.attrib)
                tags = {child.tag.rsplit("}", 1)[-1] for child in svg.iter()}
                self.assertNotIn("image", tags)
                self.assertNotIn("script", tags)
                self.assertNotIn("text", tags)
                self.assertIn("path", tags)
                self.assertNotIn("http://", data.replace("http://www.w3.org/2000/svg", ""))
                self.assertNotIn("url(", data)
        self.assertIn("WG Deck app icon", (brand_dir / "wg-deck-app.svg").read_text("utf-8"))
        installer = (ROOT / "scripts/install_desktop.sh").read_text("utf-8")
        self.assertIn("wg-deck-app.svg", installer)
        self.assertIn("Icon=wg-deck", installer)


if __name__ == "__main__":
    unittest.main()
