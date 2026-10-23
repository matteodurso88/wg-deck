"""Offline tests: optional connection confirmation and scoped Polkit auth cache.

Does not execute system connections or read private WireGuard profiles.
"""
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
SPEC = importlib.util.spec_from_file_location(
    "wgdeck_connection_test", ROOT / "privileged" / "wgdeck_connection.py"
)
assert SPEC is not None and SPEC.loader is not None
connection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(connection)


class ConnectionAuthorizationTests(unittest.TestCase):
    def test_two_policies_separate_connection_cache_from_config_authority(self):
        root = ET.parse(ROOT / "privileged" / "org.matt88.wgdeck.policy").getroot()
        conn = ET.parse(ROOT / "privileged" / "org.matt88.wgdeck.connection.policy").getroot()
        root_action = root.find("action")
        conn_action = conn.find("action")
        self.assertEqual(root_action.get("id"), "org.matt88.wgdeck.manage")
        self.assertEqual(conn_action.get("id"), "org.matt88.wgdeck.connection")
        self.assertEqual(root_action.findtext("defaults/allow_active"), "auth_admin")
        self.assertEqual(conn_action.findtext("defaults/allow_active"), "auth_admin_keep")
        for action in (root_action, conn_action):
            self.assertEqual(action.findtext("defaults/allow_any"), "no")
            self.assertEqual(action.findtext("defaults/allow_inactive"), "no")
        self.assertEqual(
            conn_action.find("annotate").text,
            "/usr/local/libexec/wg-deck-connection",
        )

    def test_dedicated_entrypoint_accepts_only_safe_up_down(self):
        with patch.object(connection.os, "geteuid", return_value=0), patch.object(
            connection.os, "execv"
        ) as execv:
            for action in ("up", "down"):
                with patch.object(connection.sys, "argv", ["wgdeck_connection", action, "demo-lab"]):
                    self.assertEqual(connection.main(), 1)
                    execv.assert_called_with(connection.ROOT_HELPER,
                                             (connection.ROOT_HELPER, action, "demo-lab"))
            count = execv.call_count
            for action, name in (
                ("install", "demo-lab"), ("replace", "demo-lab"),
                ("down", "../unsafe"), ("up", "too-long-profile-name"), ("up", ".."),
            ):
                with patch.object(connection.sys, "argv", ["wgdeck_connection", action, name]):
                    self.assertEqual(connection.main(), 2)
            self.assertEqual(execv.call_count, count)

    def test_connection_and_config_requests_use_separate_pkexec_paths(self):
        result = subprocess.CompletedProcess((), 0, b"OK:up\n", b"")
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "connection_available", return_value=True
        ), patch.object(privileged.subprocess, "run", return_value=result) as run:
            self.assertTrue(privileged.execute("up", "demo-lab").ok)
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.CONNECTION_HELPER)))
            self.assertEqual(run.call_args.args[0][2:], ("up", "demo-lab"))
            self.assertEqual(run.call_args.kwargs["input"], b"")

            run.return_value = subprocess.CompletedProcess((), 0, b"OK:installed\n", b"")
            self.assertTrue(privileged.execute("install", "demo-lab", "safe fixture").ok)
            self.assertEqual(run.call_args.args[0][:2],
                             ("pkexec", str(privileged.HELPER)))
            self.assertEqual(run.call_args.kwargs["input"], b"safe fixture")

        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "connection_available", return_value=False
        ), patch.object(privileged.subprocess, "run") as run:
            self.assertFalse(privileged.execute("down", "demo-lab").ok)
            run.assert_not_called()

    def test_confirmation_toggle_is_persisted_and_never_bypasses_privilege(self):
        code = r"""
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
from wg_deck.ui.window import MainWindow

app = QApplication([])
window = MainWindow(demo=True)
window.show()
app.processEvents()
assert window.confirm_connection_switch.isEnabled()
assert window.confirm_connection_switch.isChecked()
assert window.preferences.value("confirm_connection_changes", True, bool) is True

# Test the routing path only; never invoke the privileged helper.
window.demo = False
operations = []
window._start_operation = lambda action, name, *unused: operations.append((action, name))
with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question:
    window.request_operation("up", "demo-lab")
    assert question.call_count == 1
    assert operations == []

window.confirm_connection_switch.setChecked(False)
assert window.preferences.value("confirm_connection_changes", True, bool) is False
with patch.object(QMessageBox, "question") as question:
    window.request_operation("up", "demo-lab")
    window.request_operation("down", "demo-lab")
    question.assert_not_called()
assert operations == [("up", "demo-lab"), ("down", "demo-lab")]

window.confirm_connection_switch.setChecked(True)
with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
    window.request_operation("down", "demo-lab")
assert operations[-1] == ("down", "demo-lab")
window.preferences.sync()
window.close()
"""
        with tempfile.TemporaryDirectory() as folder:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = folder
            env.pop("PYTHONPATH", None)
            completed = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=40,
                env=env, check=False,
            )
        self.assertEqual(completed.returncode, 0,
                         f"Settings/confirmation smoke: {completed.stdout}\n{completed.stderr}")


if __name__ == "__main__":
    unittest.main()
