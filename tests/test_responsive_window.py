"""Responsive layout regression smoke (no real WireGuard operations)."""
from __future__ import annotations

import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ResponsiveWindowTests(unittest.TestCase):
    def test_editor_and_overviews_reflow_without_losing_draft(self):
        code = r"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QBoxLayout, QScrollArea, QHeaderView, QPushButton
from wg_deck.ui.window import MainWindow
from wg_deck.ui.theme import ThemeMode

app = QApplication([])
window = MainWindow(demo=True)
window.show()
window.resize(1420, 1000)
window.new_profile()
window.profile_name.setText("labtest")
window.address.setText("10.8.0.2/32")
window.listen_port.setValue(51820)
app.processEvents()

assert window.editor_split.direction() == QBoxLayout.Direction.LeftToRight
assert window.sidebar_frame.width() == 184
assert not window.dashboard_table.isColumnHidden(2)
assert window.dashboard_table.horizontalHeader().sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
assert window.settings_grid.itemAtPosition(1, 1).widget() is window.settings_cards[3]

# Action buttons must be *reused*, not overlaid in old viewport positions.
for table in (window.dashboard_table, window.profiles_table):
    initial_widgets = [table.cellWidget(row, 5) for row in range(table.rowCount())]
    assert all(widget is not None for widget in initial_widgets)
    for _ in range(4):
        window.fill_tables()
    app.processEvents()
    assert all(table.cellWidget(row, 5) is widget
               for row, widget in enumerate(initial_widgets))
    assert len(table.findChildren(QPushButton, "profileToggle")) == table.rowCount()
    assert len(table.findChildren(QPushButton, "profileEdit")) == table.rowCount()
editor_scroll = window.profiles_stack.widget(1)
assert isinstance(editor_scroll, QScrollArea)
assert editor_scroll.horizontalScrollBar().maximum() == 0

# At a narrow window the editor is stacked, important table data remain
# visible, and the user is allowed to scroll vertically rather than clip.
window.resize(1000, 720)
app.processEvents()
assert window.editor_split.direction() == QBoxLayout.Direction.TopToBottom
assert window.sidebar_frame.width() == 160
for table in (window.dashboard_table, window.profiles_table):
    for col in (2, 3, 4):
        assert table.isColumnHidden(col)
    assert not table.isColumnHidden(0)
    assert not table.isColumnHidden(1)
    assert not table.isColumnHidden(5)
    assert table.horizontalHeader().sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert table.horizontalHeader().sectionResizeMode(5) == QHeaderView.ResizeMode.Fixed
    assert table.columnWidth(5) == table.ACTION_COLUMN_WIDTH
assert window.settings_grid.itemAtPosition(3, 0).widget() is window.settings_cards[3]
assert editor_scroll.horizontalScrollBar().maximum() == 0
assert window.profile_name.text() == "labtest"
assert window.address.text() == "10.8.0.2/32"
assert window.listen_port.value() == 51820

# Theme transitions must not reset the editor.
for mode in (ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM):
    window.theme.set_mode(mode)
    app.processEvents()
    assert window.profile_name.text() == "labtest"
    assert window.profiles_stack.currentIndex() == 1

window.resize(1420, 1000)
app.processEvents()
assert window.editor_split.direction() == QBoxLayout.Direction.LeftToRight
assert not window.dashboard_table.isColumnHidden(2)
assert window.dashboard_table.horizontalHeader().sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
assert window.dashboard_table.horizontalHeader().sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
assert window.profile_name.text() == "labtest"
window.close()
"""
        with TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = temp
            env.pop("PYTHONPATH", None)
            outcome = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, env=env, timeout=40,
                check=False,
            )
        self.assertEqual(
            outcome.returncode, 0,
            f"Responsive Qt smoke failed:\n{outcome.stdout}\n{outcome.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
