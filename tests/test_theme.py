"""Theme switching, preference persistence and background fidelity smoke."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

from wg_deck.ui.theme import (
    DARK, LIGHT, ThemeMode, effective_mode, parse_mode, stylesheet,
)


class ThemeContractTests(unittest.TestCase):
    def test_light_red_is_locked_and_dark_has_independent_surfaces(self):
        self.assertEqual(LIGHT.accent, "#C91026")
        self.assertEqual(LIGHT.surface, "#FFFFFF")
        self.assertNotEqual(DARK.background, LIGHT.background)
        self.assertNotEqual(DARK.input, LIGHT.input)
        self.assertIn(LIGHT.background, stylesheet(LIGHT))
        self.assertIn(DARK.background, stylesheet(DARK))
        self.assertIn("QWidget#pageCanvas", stylesheet(LIGHT))

    def test_modes_fallback_and_system_mapping(self):
        self.assertEqual(parse_mode("light"), ThemeMode.LIGHT)
        self.assertEqual(parse_mode("dark"), ThemeMode.DARK)
        self.assertEqual(parse_mode("system"), ThemeMode.SYSTEM)
        self.assertEqual(parse_mode("invalid"), ThemeMode.SYSTEM)
        self.assertEqual(effective_mode(ThemeMode.SYSTEM, False), ThemeMode.LIGHT)
        self.assertEqual(effective_mode(ThemeMode.SYSTEM, True), ThemeMode.DARK)
        self.assertEqual(effective_mode(ThemeMode.LIGHT, True), ThemeMode.LIGHT)
        self.assertEqual(effective_mode(ThemeMode.DARK, False), ThemeMode.DARK)

    def test_persistent_theme_and_four_navigation_pages_offscreen(self):
        code = """
from pathlib import Path
from tempfile import TemporaryDirectory
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from wg_deck.ui.window import MainWindow
from wg_deck.ui.theme import ThemeMode

app = QApplication([])
window = MainWindow(demo=True)
window.show()
app.processEvents()
assert window.pages.count() == 4
combo = window.theme_choice
assert combo.count() == 3
for mode in ("light", "dark", "system"):
    index = combo.findData(mode)
    assert index >= 0
    combo.setCurrentIndex(index)
    app.processEvents()
    assert window.theme.mode.value == mode
    assert window.preferences.value("theme_mode") == mode
    for page in range(4):
        window.go(page)
        app.processEvents()
        assert window.pages.currentIndex() == page
for mode in ("light", "dark"):
    window.theme.set_mode(ThemeMode(mode))
    window.go(0)
    app.processEvents()
    image = window.grab().toImage()
    assert image.width() >= 940 and image.height() >= 630
    pixel = image.pixelColor(image.width() - 65, image.height() - 100)
    lightness = pixel.lightness()
    if mode == "light":
        assert lightness > 185, (mode, pixel.name())
    else:
        assert lightness < 110, (mode, pixel.name())
window.theme.set_mode(ThemeMode.LIGHT)
assert window.preferences.value("theme_mode") == "light"
window.close()
"""
        # XDG isolation must be set before QApplication exists.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as home:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = home
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", code],
                env=env, capture_output=True, text=True, timeout=45, check=False,
            )
        self.assertEqual(
            result.returncode, 0,
            f"Theme integration failed:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
