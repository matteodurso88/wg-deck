"""Qt icon smoke with an offscreen platform; never opens a desktop window."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class QtIconTests(unittest.TestCase):
    def test_icon_has_pixmaps_without_a_desktop_icon_theme(self):
        code = (
            "from PySide6.QtWidgets import QApplication; "
            "from wg_deck.qt_icon import make_app_icon; "
            "app=QApplication([]); "
            "icon=make_app_icon(); "
            "assert not icon.isNull(), 'app icon is null'; "
            "assert not icon.pixmap(16, 16).isNull(), '16px tray icon is null'; "
            "assert not icon.pixmap(64, 64).isNull(), '64px window icon is null'"
        )
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Qt offscreen icon smoke failed:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
