"""Offline secure native ZIP backup, import and Qt action dispatch regression."""
from __future__ import annotations

import base64
import io
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from wg_deck.core import privileged
from wg_deck.core.profile_bundle import (
    BundleError, preview_bundle, save_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wgdeck_bundle_helper", ROOT / "privileged" / "wgdeck_helper.py"
)
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def profile(private_num=1, public_num=2):
    p = base64.b64encode(bytes([private_num] * 32)).decode()
    q = base64.b64encode(bytes([public_num] * 32)).decode()
    return (
        "[Interface]\n"
        f"PrivateKey = {p}\nAddress = 198.18.77.2/32\n"
        "[Peer]\n"
        f"PublicKey = {q}\nAllowedIPs = 198.18.77.1/32\n"
    ).encode("ascii")


def archive_of(items):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in items:
            z.writestr(name, data)
    return stream.getvalue()


class BundleCoreTests(unittest.TestCase):
    def test_unprivileged_secret_archive_writes_exclusively_0600(self):
        data = archive_of([("demo-vpn.conf", profile())])
        self.assertEqual(preview_bundle(data), ("demo-vpn.conf",))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "backup.zip"
            with patch("wg_deck.core.profile_bundle.os.geteuid", return_value=1000):
                self.assertEqual(save_bundle(data, target, allowed_root=Path(directory)), target)
                self.assertEqual(target.read_bytes(), data)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                with self.assertRaises(BundleError):
                    save_bundle(data, target, allowed_root=Path(directory))
            self.assertEqual(target.read_bytes(), data)

    def test_traversal_duplicates_and_hooks_fail_closed(self):
        for items in (
            [("../oops.conf", profile())],
            [("demo-vpn.conf", profile()), ("demo-vpn.conf", profile())],
            [("demo-vpn.conf", profile().replace(b"[Peer]\n", b"PostUp = touch /tmp/x\n[Peer]\n"))],
        ):
            with self.subTest(items=len(items)), self.assertRaises(BundleError):
                preview_bundle(archive_of(items))

    def test_root_export_contains_every_native_file_including_advanced(self):
        with tempfile.TemporaryDirectory() as folder:
            root, run = Path(folder) / "etc", Path(folder) / "run"
            root.mkdir()
            run.mkdir()
            simple = profile()
            complex_config = b"[Interface]\n# Advanced Linux profile\nTable = off\nPostUp = echo hi\n"
            (root / "demo-lab.conf").write_bytes(simple)
            (root / "demo-vpn.conf").write_bytes(complex_config)
            sink = io.BytesIO()
            stdout = type("Stdout", (), {"buffer": sink})()
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", run),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "secure_directory"),
                patch.object(helper, "secure_file", side_effect=lambda p: Path(p).read_bytes()),
                patch.object(helper.sys, "stdout", stdout),
            ):
                helper.handle("bundle", "all")
            raw = sink.getvalue()
            self.assertTrue(raw.startswith(b"OK:bundle\n"))
            with zipfile.ZipFile(io.BytesIO(raw[len(b"OK:bundle\n"):])) as bundle:
                self.assertEqual(set(bundle.namelist()), {"demo-lab.conf", "demo-vpn.conf"})
                self.assertEqual(bundle.read("demo-vpn.conf"), complex_config)
            # Never print archive content in repr/logs.
            self.assertNotIn("PrivateKey", repr(privileged.BundleResult(True, "OK", raw)))

    def test_root_import_all_new_profiles_atomically_without_overwrites(self):
        data = archive_of([("wg-one.conf", profile()), ("wg-two.conf", profile(3, 4))])
        with tempfile.TemporaryDirectory() as folder:
            root, run = Path(folder) / "etc", Path(folder) / "run"
            root.mkdir()
            run.mkdir()
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", run),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "secure_directory"),
            ):
                helper.handle("install-bundle", "all", data)
                self.assertEqual((root / "wg-one.conf").read_bytes(), profile())
                self.assertEqual((root / "wg-two.conf").read_bytes(), profile(3, 4))
                self.assertEqual(stat.S_IMODE((root / "wg-one.conf").stat().st_mode), 0o600)
                with self.assertRaises(helper.Rejected):
                    helper.handle("install-bundle", "all", data)
                # One name already exists: absolutely no partial import.
                with self.assertRaises(helper.Rejected):
                    helper.handle("install-bundle", "all", archive_of([
                        ("wg-two.conf", profile(3, 4)), ("wg-three.conf", profile())
                    ]))
                self.assertFalse((root / "wg-three.conf").exists())

    def test_polkit_archive_is_single_authorized_action_not_per_profile(self):
        stream = archive_of([("demo-vpn.conf", profile()), ("demo-lab.conf", profile(3, 4))])
        completed = subprocess.CompletedProcess((), 0, b"OK:bundle\n" + stream, b"")
        # The scoped read policy may or may not be installed on the test host.
        # Pin the authorization path so this regression is deterministic.
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "read_available", return_value=True
        ), patch.object(
            privileged.subprocess, "run", return_value=completed
        ) as run:
            result = privileged.read_bundle()
            self.assertTrue(result.ok)
            self.assertEqual(result.data, stream)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], (
                "pkexec", str(privileged.READ_HELPER), "bundle", "all"
            ))

        # Before the scoped reader is installed, retain the strict helper.
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "read_available", return_value=False
        ), patch.object(
            privileged.subprocess, "run", return_value=completed
        ) as run:
            result = privileged.read_bundle()
            self.assertTrue(result.ok)
            self.assertEqual(result.data, stream)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], (
                "pkexec", str(privileged.HELPER), "bundle", "all"
            ))

        # Installing an archive must never inherit the cached read permission.
        completed.stdout = b"OK:imported:2\n"
        with patch.object(privileged, "available", return_value=True), patch.object(
            privileged, "read_available", return_value=True
        ), patch.object(
            privileged.subprocess, "run", return_value=completed
        ) as run:
            result = privileged.install_bundle(stream)
            self.assertTrue(result.ok)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], (
                "pkexec", str(privileged.HELPER), "install-bundle", "all"
            ))
            self.assertEqual(run.call_args.kwargs["input"], stream)

    def test_rows_and_toolbar_have_distinct_commands_offscreen(self):
        script = r"""
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QPushButton
from wg_deck.ui.window import MainWindow
app = QApplication([])
window = MainWindow(demo=True)
window.show()
buttons = [button.text() for button in window.findChildren(QPushButton)]
assert "Export All" in buttons and "Import Backup" in buttons
assert "Delete" not in buttons
holder = window.profiles_table.cellWidget(0, 5)
assert holder.findChild(QPushButton, "profileExport")
assert holder.findChild(QPushButton, "profileDelete")
for title in ("profileToggle", "profileEdit", "profileExport", "profileDelete"):
    assert holder.findChild(QPushButton, title).property("wgmProfile") == "office-vpn" or title in ("profileToggle", "profileEdit")
assert not holder.findChild(QPushButton, "profileExport").isEnabled()
assert not holder.findChild(QPushButton, "profileDelete").isEnabled()
window.close()
"""
        with tempfile.TemporaryDirectory() as temp:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = temp
            env.pop("PYTHONPATH", None)
            proc = subprocess.run([sys.executable, "-c", script], env=env,
                                  capture_output=True, text=True, check=False, timeout=40)
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)


if __name__ == "__main__":
    unittest.main()
