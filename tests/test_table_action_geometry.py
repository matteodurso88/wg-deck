"""Qt geometry guard for the real Profiles actions clipping regression.

All fixtures are demo data. No privileged WireGuard commands are called.
"""
from __future__ import annotations

import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ProfileActionGeometryTests(unittest.TestCase):
    def test_actions_fit_inside_last_column_at_both_viewport_sizes(self):
        code = r"""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QPushButton
from wg_deck.ui.window import MainWindow, ProfileTable
from wg_deck.ui.theme import ThemeMode

app = QApplication([])
window = MainWindow(demo=True)
window.show()

def check(table):
    header = table.horizontalHeader()
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Fixed
    assert table.columnWidth(5) == ProfileTable.ACTION_COLUMN_WIDTH
    assert table.horizontalScrollBar().maximum() == 0
    original = [table.cellWidget(row, 5) for row in range(table.rowCount())]
    assert len(original) == 5
    for _ in range(3):
        window.fill_tables()
    app.processEvents()
    for row, holder in enumerate(original):
        assert table.cellWidget(row, 5) is holder
        assert holder is not None and holder.width() >= 190, (
            "action cell shrunk", holder.size(), table.columnWidth(5)
        )
        toggle = holder.findChild(QPushButton, "profileToggle")
        edit = holder.findChild(QPushButton, "profileEdit")
        export = holder.findChild(QPushButton, "profileExport")
        delete = holder.findChild(QPushButton, "profileDelete")
        assert all(button is not None for button in (toggle, edit, export, delete))
        assert toggle.text() in ("Connect", "Disconnect")
        assert edit.accessibleName() == "Edit WireGuard profile"
        assert export.accessibleName() == "Export WireGuard profile"
        assert delete.accessibleName() == "Delete WireGuard profile"
        assert not toggle.isEnabled() and edit.isEnabled()
        assert not export.isEnabled() and not delete.isEnabled()  # demo safety
        assert table.rowHeight(row) >= ProfileTable.ACTION_ROW_HEIGHT, (
            "row height", row, table.rowHeight(row), ProfileTable.ACTION_ROW_HEIGHT
        )
        # GNOME/Qt QSS may slightly adjust a requested fixed button size.
        # The real invariant is that each control is visible and fits its cell.
        # Pixel-exact equality made Dell fail before testing containment.
        assert 24 <= toggle.height() <= holder.height(), (
            "toggle height invalid", row, toggle.height(), holder.height()
        )
        assert 24 <= edit.height() <= holder.height(), (
            "edit height invalid", row, edit.height(), holder.height()
        )
        for button in (toggle, edit, export, delete):
            pos = button.mapTo(holder, QPoint(0, 0))
            assert pos.x() >= 0 and pos.y() >= 0, (row, button.text(), pos)
            assert pos.x() + button.width() <= holder.width(), (
                row, button.text(), button.geometry(), holder.size()
            )
            assert pos.y() + button.height() <= holder.height(), (
                row, button.text(), button.geometry(), holder.size()
            )
        ordered = (toggle, edit, export, delete)
        for left, right in zip(ordered, ordered[1:]):
            assert right.x() >= left.x() + left.width(), (
                "buttons overlap", row, left.geometry(), right.geometry(), holder.geometry()
            )
    assert table.height() <= 390, ("excess empty table height", table.height())

for width, height, compact in ((1400, 920, False), (1000, 720, True)):
    window.resize(width, height)
    app.processEvents()
    for theme in (ThemeMode.LIGHT, ThemeMode.DARK):
        window.theme.set_mode(theme)
        app.processEvents()
        for page, table in ((0, window.dashboard_table), (1, window.profiles_table)):
            window.go(page)
            app.processEvents()
            assert not table.isColumnHidden(5)
            check(table)
            if compact:
                assert table.horizontalHeader().sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
            else:
                assert table.horizontalHeader().sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
window.close()
"""
        with TemporaryDirectory() as temporary:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = temporary
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                env=env,
                timeout=50,
                check=False,
            )
        self.assertEqual(
            result.returncode, 0,
            f"Table action geometry regression:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
