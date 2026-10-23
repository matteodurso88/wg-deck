"""Desktop action parity and scoped Polkit authorization tests (OFFLINE)."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from wg_deck.core import privileged

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("read_only_entry", ROOT / "privileged" / "wgdeck_read.py")
assert spec is not None and spec.loader is not None
read_entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(read_entry)


class ReadOnlyPolkitTests(unittest.TestCase):
    def test_read_policy_cache_is_scoped_to_secrets_without_write_rights(self):
        policy = ET.parse(ROOT / "privileged" / "org.matt88.wgdeck.read.policy").getroot()
        action = policy.find("action")
        self.assertEqual(action.get("id"), "org.matt88.wgdeck.read")
        self.assertEqual(action.findtext("defaults/allow_active"), "auth_admin_keep")
        self.assertEqual(action.findtext("defaults/allow_any"), "no")
        self.assertEqual(action.findtext("defaults/allow_inactive"), "no")
        self.assertEqual(action.find("annotate").text, str(privileged.READ_HELPER))
        managed = ET.parse(ROOT / "privileged" / "org.matt88.wgdeck.policy").getroot()
        self.assertEqual(managed.find("action/defaults/allow_active").text, "auth_admin")

    def test_read_dispatcher_only_allows_read_and_bundle(self):
        with patch.object(read_entry.os, "geteuid", return_value=0), patch.object(
            read_entry.os, "execv"
        ) as execute:
            for action, name in (("read", "demo-vpn"), ("bundle", "all")):
                with patch.object(read_entry.sys, "argv", ["read", action, name]):
                    self.assertEqual(read_entry.main(), 1)
                    execute.assert_called_with(read_entry.ROOT_HELPER, (
                        read_entry.ROOT_HELPER, action, name
                    ))
            calls = execute.call_count
            for action, name in (
                ("delete", "demo-vpn"), ("replace", "demo-vpn"),
                ("install-bundle", "all"), ("up", "demo-vpn"),
                ("read", "../unsafe"), ("bundle", "demo-vpn"),
            ):
                with patch.object(read_entry.sys, "argv", ["read", action, name]):
                    self.assertEqual(read_entry.main(), 2)
            self.assertEqual(execute.call_count, calls)

    def test_read_and_export_use_short_cache_write_stays_strict(self):
        def result_for(code):
            return subprocess.CompletedProcess((), 0, code, b"")
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "read_available", return_value=True
        ), patch.object(privileged.subprocess, "run") as run:
            run.return_value = result_for(b"OK:read\n[Interface]\n")
            self.assertTrue(privileged.read_profile("demo-vpn").ok)
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.READ_HELPER)))
            run.return_value = result_for(b"OK:bundle\n" + b"PK")
            self.assertTrue(privileged.read_bundle().ok)
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.READ_HELPER)))
            run.return_value = result_for(b"OK:deleted\n")
            self.assertTrue(privileged.execute("delete", "wgdeck-test").ok)
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.HELPER)))

        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "read_available", return_value=False
        ), patch.object(privileged.subprocess, "run", return_value=result_for(
            b"OK:read\n[Interface]\n"
        )) as run:
            self.assertTrue(privileged.read_profile("demo-vpn").ok)
            # Uninstalled scoped reader retains the existing strict flow.
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.HELPER)))


class DashboardRowParityTests(unittest.TestCase):
    def test_all_four_buttons_dispatch_equally_in_dashboard_and_profiles(self):
        code = r"""
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from wg_deck.ui.window import MainWindow

app = QApplication([])
window = MainWindow(demo=True)
window.show()
window.demo = False
window.preferences.setValue("confirm_connection_changes", False)
window.preferences.sync()
with patch("wg_deck.ui.window.connection_available", return_value=True), patch(
    "wg_deck.ui.window.helper_available", return_value=True
):
    window.fill_tables()
    app.processEvents()
    for index, table in ((0, window.dashboard_table), (1, window.profiles_table)):
        window.go(index)
        app.processEvents()
        holder = table.cellWidget(1, 5)  # demo home-lab is DOWN
        assert holder is not None
        toggle = holder.findChild(QPushButton, "profileToggle")
        edit = holder.findChild(QPushButton, "profileEdit")
        export = holder.findChild(QPushButton, "profileExport")
        delete = holder.findChild(QPushButton, "profileDelete")
        assert all(button.isEnabled() for button in (toggle, edit, export, delete))
        assert all(button.property("wgmProfile") == "home-lab"
                   for button in (toggle, edit, export, delete))
        with patch.object(window, "_start_operation") as command:
            toggle.click()
            command.assert_called_once_with("up", "home-lab")
        with patch.object(window, "_start_system_read") as read:
            edit.click()
            read.assert_called_once_with("read", "home-lab")
        with patch.object(window, "_start_system_read") as read:
            export.click()
            read.assert_called_once_with("export", "home-lab")
        with patch.object(QMessageBox, "warning",
                          return_value=QMessageBox.StandardButton.Yes):
            with patch.object(window, "_start_operation") as command:
                delete.click()
                command.assert_called_once_with("delete", "home-lab")
window.close()
"""
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = temp
            env.pop("PYTHONPATH", None)
            finished = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True,
                env=env, timeout=45, check=False,
            )
        self.assertEqual(finished.returncode, 0,
                         f"Dashboard parity failed:\n{finished.stdout}\n{finished.stderr}")


if __name__ == "__main__":
    unittest.main()
