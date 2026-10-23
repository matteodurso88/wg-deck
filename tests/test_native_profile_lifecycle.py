"""Native-profile parity and deletion tests. Fully offline, no system writes."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wg_deck.core import privileged

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_delete_helper", ROOT / "privileged" / "wgdeck_helper.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class NativeHelperLifecycleTests(unittest.TestCase):
    def test_safe_file_allows_root_owned_bash_profile_when_not_world_writable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "demo-vpn.conf"
            path.write_bytes(b"[Interface]\n# native Bash profile\n")
            real = path.stat()
            for mode, allowed in ((0o600, True), (0o640, True), (0o644, True), (0o660, False), (0o666, False)):
                path.chmod(mode)
                fixture = SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=0, st_size=real.st_size)
                with patch.object(helper.os, "fstat", return_value=fixture):
                    if allowed:
                        self.assertEqual(helper.secure_file(path), path.read_bytes())
                    else:
                        with self.assertRaises(helper.Rejected):
                            helper.secure_file(path)

    def test_delete_native_profile_saves_root_only_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "etc-wireguard"
            root.mkdir()
            runtime = Path(folder) / "run"
            runtime.mkdir()
            text = b"[Interface]\n# native profile from Bash\nPrivateKey = fake-secret\n"
            target = root / "demo-vpn.conf"
            target.write_bytes(text)
            def secure(path):
                return Path(path).read_bytes()
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", runtime),
                patch.object(helper, "secure_directory", side_effect=lambda p: p.mkdir(exist_ok=True)),
                patch.object(helper, "secure_file", side_effect=secure),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "is_up", return_value=False),
                patch.object(helper, "systemd_is", return_value=False),
            ):
                helper.handle("delete", "demo-vpn")
            self.assertFalse(target.exists())
            backups = list((root / ".wg-deck-backups").glob("*.conf"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), text)
            self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)

    def test_delete_rejects_active_enabled_and_nonexistent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime = root / ".runtime"
            runtime.mkdir()
            path = root / "demo-vpn.conf"
            path.write_bytes(b"native")
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", runtime),
                patch.object(helper, "secure_directory"),
                patch.object(helper, "secure_file", return_value=b"native"),
                patch.object(helper.os, "geteuid", return_value=0),
            ):
                with patch.object(helper, "is_up", return_value=True):
                    with self.assertRaises(helper.Rejected):
                        helper.handle("delete", "demo-vpn")
                with patch.object(helper, "is_up", return_value=False), patch.object(
                    helper, "systemd_is", side_effect=lambda name, check: check == "is-enabled"
                ):
                    with self.assertRaises(helper.Rejected):
                        helper.handle("delete", "demo-vpn")
            self.assertTrue(path.exists())
            self.assertFalse((root / ".wg-deck-backups").exists())

    def test_bridge_routes_delete_via_strict_per_operation_helper(self):
        result = subprocess.CompletedProcess((), 0, b"OK:deleted\n", b"")
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged.subprocess, "run", return_value=result
        ) as run:
            self.assertTrue(privileged.execute("delete", "demo-vpn").ok)
            self.assertEqual(run.call_args.args[0][:4], (
                "pkexec", str(privileged.HELPER), "delete", "demo-vpn"
            ))
            self.assertEqual(run.call_args.kwargs["input"], b"")

    def test_failure_message_is_safe_and_actionable(self):
        case = subprocess.CompletedProcess((), 1, b"", b"ERR:Unsafe config owner or writable permissions.\n")
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged.subprocess, "run", return_value=case
        ):
            read = privileged.read_profile("demo-vpn")
            self.assertFalse(read.ok)
            self.assertIn("Unsafe config owner", read.message)
        case.stderr = b"ERR:PrivateKey = do-not-leak\n"
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged.subprocess, "run", return_value=case
        ):
            read = privileged.read_profile("demo-vpn")
            self.assertNotIn("do-not-leak", read.message)


class NativeUIFlowTests(unittest.TestCase):
    def test_row_export_delete_and_safety_offscreen(self):
        code = r"""
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from wg_deck.ui.window import MainWindow
from wg_deck.core.discovery import Inventory
from wg_deck.core.models import ProfileSnapshot, TunnelState

app = QApplication([])
window = MainWindow(demo=True)
window.show()
window.inventory = Inventory((
    ProfileSnapshot("demo-vpn", TunnelState.DOWN),
    ProfileSnapshot("demo-lab", TunnelState.DOWN),
), ())
window.fill_tables()
window.demo = False
holder = window.profiles_table.cellWidget(0, 5)
assert holder.findChild(QPushButton, "profileExport").property("wgmProfile") == "demo-vpn"
assert holder.findChild(QPushButton, "profileDelete").property("wgmProfile") == "demo-vpn"

with patch.object(window, "_start_system_read") as reader:
    window.export_profile("demo-vpn")
    reader.assert_called_once_with("export", "demo-vpn")

with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
    with patch("wg_deck.ui.window.helper_available", return_value=True):
        with patch.object(window, "_start_operation") as action:
            window.delete_profile("demo-vpn")
            action.assert_called_once_with("delete", "demo-vpn")

window.inventory = Inventory((ProfileSnapshot("demo-vpn", TunnelState.UP),), ())
window.fill_tables()
with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
    with patch("wg_deck.ui.window.helper_available", return_value=True):
        with patch.object(window, "_start_operation") as action:
            window.delete_profile("demo-vpn")
            action.assert_not_called()
window.close()
"""
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=tmp)
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True,
                env=env, timeout=40, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)


    def test_import_preserves_supported_crlf_comments_and_field_edits(self):
        source = r"""
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from wg_deck.ui.window import MainWindow
from wg_deck.core.profile_export import parse_supported_profile

app = QApplication([])
window = MainWindow(demo=True)
window.show()
key_a = base64.b64encode(bytes([1] * 32)).decode("ascii")
key_b = base64.b64encode(bytes([2] * 32)).decode("ascii")
original = (
    "# Do not discard me\r\n"
    "[Interface]\r\n"
    "Address = 198.18.77.2/32\r\n"
    f"PrivateKey = {key_a}\r\n"
    "\r\n"
    "[Peer]\r\n"
    f"PublicKey = {key_b}\r\n"
    "AllowedIPs = 198.18.77.1/32\r\n"
    "# Keep this peer comment\r\n"
)
with TemporaryDirectory() as folder:
    path = Path(folder) / "wgdeck-import.conf"
    path.write_bytes(original.encode("utf-8"))
    with patch.object(QFileDialog, "getOpenFileName", return_value=(str(path), "WireGuard profile (*.conf)")):
        window.import_config()
    assert window.import_original == original
    assert window.import_source_name == "wgdeck-import"
    assert not window.imported_profile
    window.demo = False
    with patch("wg_deck.ui.window.helper_available", return_value=True):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            with patch.object(window, "_start_operation") as start:
                window.install_new_profile()
                action, name, rendered = start.call_args.args
                assert (action, name) == ("install", "wgdeck-import")
                assert rendered == original, "Unmodified native import must preserve bytes"
                start.reset_mock()
                window.dns.setText("1.1.1.1")
                window.install_new_profile()
                action, name, rendered = start.call_args.args
                assert "# Do not discard me\r\n" in rendered
                assert "# Keep this peer comment\r\n" in rendered
                assert "\r\nDNS = 1.1.1.1\r\n" in rendered
                assert parse_supported_profile(name, rendered).dns == "1.1.1.1"
window.close()
"""
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=tmp)
            env.pop("PYTHONPATH", None)
            process = subprocess.run(
                [sys.executable, "-c", source], capture_output=True,
                text=True, env=env, timeout=40, check=False,
            )
        self.assertEqual(process.returncode, 0, process.stdout + "\n" + process.stderr)


if __name__ == "__main__":
    unittest.main()
