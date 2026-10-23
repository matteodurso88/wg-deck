"""Qt offscreen smoke verifies all pages without touching wg or any real profile."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class MainWindowTests(unittest.TestCase):
    def test_canonical_pages_and_demo_are_renderable_offscreen(self):
        code = (
            "from PySide6.QtWidgets import QApplication; "
            "from wg_deck.ui.window import MainWindow; "
            "app=QApplication([]); "
            "window=MainWindow(demo=True); "
            "assert window.pages.count() == 4; "
            "assert window.inventory.profiles[0].name == 'office-vpn'; "
            "assert len(window.metric_details) == 4; "
            "assert window.metric_details[0].text() == '3 connected'; "
            "assert window.diag_logs.rowCount() >= 3; "
            "assert 'DEMO' in window.demo_label.text(); "
            "from PySide6.QtWidgets import QPushButton; "
            "actions=window.dashboard_table.cellWidget(0,5).findChildren(QPushButton); "
            "assert len(actions)==4 and not actions[0].isEnabled() and actions[1].isEnabled() and not actions[2].isEnabled() and not actions[3].isEnabled(); "
            "window.go(3); "
            "assert window.pages.currentIndex() == 3; "
            "window.close()"
        )
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Qt UI smoke failed: {result.stdout}\n{result.stderr}",
        )


    def test_multi_peer_draft_selection_and_removal_offscreen(self):
        code = (
            "from PySide6.QtWidgets import QApplication; "
            "from wg_deck.ui.window import MainWindow; "
            "app=QApplication([]); window=MainWindow(demo=True); "
            "window.new_profile(); assert window.pages.currentIndex()==1; assert window.profiles_stack.currentIndex()==1; "
            "window.public_key.setText('FIRST'); window.add_peer(); "
            "window.public_key.setText('SECOND'); window.add_peer(); "
            "window.public_key.setText('THIRD'); "
            "window.peer_selector.setCurrentIndex(0); "
            "assert window.public_key.text() == 'FIRST'; "
            "window.peer_selector.setCurrentIndex(1); "
            "assert window.public_key.text() == 'SECOND'; "
            "window.remove_peer(); "
            "assert len(window.peer_states) == 2; "
            "assert window.public_key.text() == 'THIRD'; "
            "window.imported_profile=True; window.add_peer(); "
            "assert len(window.peer_states) == 2; "
            "window.close()"
        )
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
            env=environment, check=False,
        )
        self.assertEqual(result.returncode, 0, f"{result.stdout}\\n{result.stderr}")


    def test_profiles_workspace_unifies_new_import_edit_and_navigation(self):
        code = (
            "from PySide6.QtWidgets import QApplication; "
            "from wg_deck.ui.window import MainWindow, NAV; "
            "app=QApplication([]); window=MainWindow(demo=True); "
            "assert NAV==('Dashboard','Profiles','Diagnostics','Settings'); "
            "assert window.pages.count()==4; "
            "assert not window.preferences.contains('known_profiles'); "
            "assert not window.preferences.contains('managed_profiles'); "
            "from PySide6.QtWidgets import QPushButton; "
            "buttons=[b.text() for b in window.findChildren(QPushButton)]; "
            "assert 'Load System' not in buttons and 'Refresh' not in buttons; "
            "assert 'Export draft .conf' not in buttons and 'Export All' in buttons and 'Import Backup' in buttons and 'Create Profile' in buttons; "
            "window.new_profile(); "
            "assert window.pages.currentIndex()==1; "
            "assert window.profiles_stack.currentIndex()==1; "
            "window.back_to_profiles(); "
            "assert window.profiles_stack.currentIndex()==0; "
            "window.go(2); assert window.pages.currentIndex()==2; "
            "window.go(3); assert window.pages.currentIndex()==3; "
            "window.close()"
        )
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, env=env, timeout=30, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)



if __name__ == "__main__":
    unittest.main()
