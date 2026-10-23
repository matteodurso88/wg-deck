"""Public WG Deck layout and identity must not regress to the private module."""
from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicLayoutTests(unittest.TestCase):
    def test_canonical_module_and_distribution_entrypoint(self):
        self.assertTrue((ROOT / "src/wg_deck/qt_app.py").is_file())
        self.assertFalse((ROOT / "src" / ("wg_" + "quick_manager")).exists())
        with (ROOT / "pyproject.toml").open("rb") as source:
            project = tomllib.load(source)["project"]
        self.assertEqual(set(project["scripts"]), {"wg-deck"})
        self.assertEqual(project["scripts"]["wg-deck"], "wg_deck.qt_app:main")

    def test_system_identifiers_use_product_name(self):
        for file in (
            "privileged/wgdeck_helper.py",
            "privileged/wgdeck_inventory.py",
            "privileged/wgdeck_connection.py",
            "privileged/wgdeck_read.py",
            "privileged/org.matt88.wgdeck.policy",
            "privileged/org.matt88.wgdeck.connection.policy",
            "privileged/org.matt88.wgdeck.read.policy",
            "privileged/wg-deck-inventory.service",
            "privileged/wg-deck-inventory.path",
            "privileged/wg-deck-inventory.timer",
        ):
            with self.subTest(path=file):
                self.assertTrue((ROOT / file).is_file())

    def test_no_outdated_technical_identifiers_in_shipped_code(self):
        old = ("wg_" + "quick_manager", "wg-" + "quick-manager",
               "org.matt88." + "wgm", "wgm" + "_", "WGM" + "-TRAFFIC")
        for folder in ("src", "scripts", "privileged"):
            for file in (ROOT / folder).rglob("*"):
                if not file.is_file() or file.suffix not in {
                    ".py", ".sh", ".policy", ".service", ".path", ".timer"
                }:
                    continue
                with self.subTest(path=str(file.relative_to(ROOT))):
                    data = file.read_text("utf-8")
                    for obsolete in old:
                        self.assertNotIn(obsolete, data)

    def test_bilingual_public_upgrade_manuals(self):
        for lang in ("en", "it"):
            self.assertTrue((ROOT / "docs" / lang / "UPGRADE.md").is_file())


if __name__ == "__main__":
    unittest.main()
