"""Regression tests for unprivileged XDG login startup and version display.

The tests only write a disposable user config directory; no VPN operations.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wg_deck import __version__
from wg_deck.core import autostart


class AutostartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "xdg-config"
        self.launcher = self.root / "project with spaces" / "scripts" / "run.sh"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("#!/bin/bash\n", encoding="utf-8")
        self.target = self.config / "autostart" / autostart.DESKTOP_FILE

    def change(self, value: bool):
        with patch.object(autostart.os, "geteuid", return_value=1000):
            return autostart.set_enabled(
                value, config_home=self.config, launcher=self.launcher
            )

    def status(self):
        return autostart.is_enabled(
            config_home=self.config, launcher=self.launcher
        )

    def test_enable_disable_are_reversible_and_never_connect_vpn(self):
        self.assertFalse(self.status())
        self.change(True)
        self.assertTrue(self.status())
        original = self.target.read_bytes()
        self.assertIn(
            f'Exec=/usr/bin/bash "{self.launcher}"'.encode("utf-8"), original
        )
        self.assertIn(b"no VPN auto-connect", original)
        self.assertNotIn(b"pkexec", original)
        self.assertNotIn(b"wg-quick up", original)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.change(True)
        self.assertEqual(self.target.read_bytes(), original)
        self.change(False)
        self.assertFalse(self.target.exists())
        self.change(False)

    def test_existing_entry_is_never_overwritten_or_removed(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"[Desktop Entry]\nName=Custom\n")
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(autostart.AutostartError):
                    self.change(value)
                self.assertEqual(
                    self.target.read_bytes(), b"[Desktop Entry]\nName=Custom\n"
                )

    def test_symlink_is_never_followed_or_removed(self):
        outside = self.root / "outside.desktop"
        outside.write_text("untouched")
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(outside)
        self.assertFalse(self.status())
        with self.assertRaises(autostart.AutostartError):
            self.change(True)
        with self.assertRaises(autostart.AutostartError):
            self.change(False)
        self.assertEqual(outside.read_text(), "untouched")
        self.assertTrue(self.target.is_symlink())

    def test_reject_bad_path_relative_xdg_and_root(self):
        with self.assertRaises(autostart.AutostartError):
            with patch.object(autostart.os, "geteuid", return_value=0):
                autostart.set_enabled(
                    True, config_home=self.config, launcher=self.launcher
                )
        with self.assertRaises(autostart.AutostartError):
            self.change_invalid_config()
        bad = self.root / "unsafe%code.sh"
        bad.write_text("#!/bin/bash\n")
        with self.assertRaises(autostart.AutostartError):
            with patch.object(autostart.os, "geteuid", return_value=1000):
                autostart.set_enabled(True, config_home=self.config, launcher=bad)
        self.assertFalse(self.target.exists())

    def change_invalid_config(self):
        with patch.object(autostart.os, "geteuid", return_value=1000):
            autostart.set_enabled(
                True, config_home=Path("relative/xdg"), launcher=self.launcher
            )

    def test_xdg_environment_is_respected(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.config)}):
            with patch.object(autostart.os, "geteuid", return_value=1000):
                autostart.set_enabled(True, launcher=self.launcher)
                self.assertTrue(autostart.is_enabled(launcher=self.launcher))
                autostart.set_enabled(False, launcher=self.launcher)
                self.assertFalse(autostart.is_enabled(launcher=self.launcher))

    def test_qt_version_and_toggle_smoke_offscreen(self):
        code = r"""
import os
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from wg_deck import __version__
from wg_deck.ui.window import MainWindow

app = QApplication([])
window = MainWindow(demo=True)
assert window.pages.count() == 4
assert window.version_label.text() == f"Version {__version__} · WG Deck"
assert f"WG Deck v{__version__}" in [
    label.text() for label in window.sidebar_frame.findChildren(
        __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
    )
]
assert window.windowTitle() == "WG Deck"
assert window.wgdeck_header_logo.accessibleName() == "WG Deck official logo"
assert window.wgdeck_header_logo.pixmap() is not None
assert not window.wgdeck_header_logo.pixmap().isNull()
assert not window.windowIcon().isNull()
assert window.sidebar_matt88_logo.accessibleName() == "Official matt88.it logo — visit website"
assert window.sidebar_matt88_logo.pixmap() is not None
assert not window.sidebar_matt88_logo.pixmap().isNull()
from wg_deck.ui.theme import ThemeMode
window.resize(1400, 920)
window.show()
app.processEvents()
for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
    window.theme.set_mode(mode)
    assert window.sidebar_matt88_logo.pixmap() is not None
    assert not window.sidebar_matt88_logo.pixmap().isNull()
    assert window.wgdeck_header_logo.pixmap() is not None
    assert not window.wgdeck_header_logo.pixmap().isNull()
assert window.sidebar_matt88_logo.width() == 86
assert abs(window.sidebar_matt88_logo.geometry().center().x() - window.sidebar_frame.rect().center().x()) <= 1
window.resize(1000, 720)
app.processEvents()
assert window.sidebar_matt88_logo.width() == 76
assert abs(window.sidebar_matt88_logo.geometry().center().x() - window.sidebar_frame.rect().center().x()) <= 1
assert window.sidebar_matt88_logo.pixmap() is not None
assert not window.sidebar_matt88_logo.pixmap().isNull()
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
window.tray = QSystemTrayIcon(window)
window.menu = QMenu(window)
window.refresh_tray()
assert window.menu.actions()[0].text() == "WG Deck"
window.tray = None
assert window.autostart_switch.accessibleName() == "Start on login (autostart)"
assert not window.autostart_switch.isEnabled()  # demo cannot mutate login
window.autostart_switch.setEnabled(True)  # isolated toggle integration
with patch("wg_deck.core.autostart.os.geteuid", return_value=1000):
    window.autostart_switch.setChecked(True)
    item = Path(os.environ["XDG_CONFIG_HOME"]) / "autostart" / "org.matt88.wg-deck.desktop"
    assert item.is_file()
    window.autostart_switch.setChecked(False)
    assert not item.exists()
window.close()
"""
        with tempfile.TemporaryDirectory() as isolated:
            env = os.environ.copy()
            env["XDG_CONFIG_HOME"] = isolated
            env["QT_QPA_PLATFORM"] = "offscreen"
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", code],
                env=env, capture_output=True, text=True, timeout=45, check=False
            )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


if __name__ == "__main__":
    unittest.main()
