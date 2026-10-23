"""Editor form control QA. Never accesses or mutates real WireGuard profiles."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest


class EditorFormControls(unittest.TestCase):
    def test_editor_controls_and_light_dark_render_offscreen(self):
        script = r"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit
from PySide6.QtGui import QValidator
from wg_deck.ui.window import MainWindow
from wg_deck.ui.widgets import CleanComboBox, NumericField
from wg_deck.ui.theme import ThemeMode

app = QApplication([])
window = MainWindow(demo=True)
window.resize(1240, 920)
window.show()
window.new_profile()
app.processEvents()

assert window.pages.currentIndex() == 1
assert window.profiles_stack.currentIndex() == 1
for item in (window.listen_port, window.mtu, window.keepalive):
    assert isinstance(item, NumericField), type(item)
    assert isinstance(item, QLineEdit)
    assert item.height() >= 38
    assert item.validator().validate("invalid", 0)[0] == QValidator.State.Invalid
assert window.listen_port.value() == 0
assert window.listen_port.text() == ""
assert window.mtu.text() == ""
assert window.keepalive.text() == ""
assert window.listen_port.placeholderText() == "Automatic"
assert window.mtu.placeholderText() == "Automatic"
assert window.keepalive.placeholderText() == "Disabled"
assert isinstance(window.peer_selector, CleanComboBox)
assert isinstance(window.theme_choice, CleanComboBox)
assert isinstance(window.peer_selector, QComboBox)
assert window.peer_selector.count() == 1
assert window.generate_keys.text() == "Generate"
assert window.copy_public_key_button.text() == "Copy"
assert not window.copy_public_key_button.isEnabled()
window.interface_public_key.setText("safe-test-public-value")
assert window.copy_public_key_button.isEnabled()
window.interface_public_key.clear()
assert not window.copy_public_key_button.isEnabled()

# The new field actions must remain next to their inputs, not occupy whole form rows.
private_parent = window.private_key.parentWidget()
public_parent = window.interface_public_key.parentWidget()
assert window.generate_keys.parentWidget() is private_parent
assert window.copy_public_key_button.parentWidget() is public_parent
assert private_parent.layout().count() == 2
assert public_parent.layout().count() == 2

window.listen_port.setValue(51820)
window.mtu.setValue(1420)
window.keepalive.setValue(25)
assert window.listen_port.value() == 51820
assert window.mtu.value() == 1420
assert window.keepalive.value() == 25
window.keepalive.clear()
assert window.keepalive.value() == 0
assert window.keepalive.placeholderText() == "Disabled"

for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
    window.theme.set_mode(mode)
    app.processEvents()
    for widget in (window.listen_port, window.mtu, window.keepalive,
                   window.peer_selector, window.private_key, window.interface_public_key):
        pixmap = widget.grab()
        assert not pixmap.isNull(), (mode, widget.objectName())
        assert pixmap.width() >= 100, (mode, widget.objectName())
    assert window.profiles_stack.currentIndex() == 1

# Peer additions and round trips must keep the existing model intact.
window.add_peer()
assert window.peer_selector.count() == 2
window.peer_selector.setCurrentIndex(0)
window.peer_selector.setCurrentIndex(1)
window.remove_peer()
assert window.peer_selector.count() == 1
window.close()
"""
        with tempfile.TemporaryDirectory() as config_dir:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = config_dir
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                env=env,
                capture_output=True,
                text=True,
                timeout=35,
                check=False,
            )
        self.assertEqual(
            result.returncode, 0,
            f"Form widget smoke failed:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
