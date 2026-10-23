"""The only profile catalogue is the native root-owned system directory.

All tests work with temporary fixtures; no privileged helper is launched.
"""
from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wg_deck.core.system_profiles import read_native_names


SOURCE = Path(__file__).resolve().parents[1] / "privileged" / "wgdeck_inventory.py"
SPEC = importlib.util.spec_from_file_location("wgdeck_native_inventory", SOURCE)
assert SPEC and SPEC.loader
PUBLISHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLISHER)


class NativeSystemInventoryTests(unittest.TestCase):
    def test_root_publisher_uses_file_names_only_and_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            configs = root / "etc_wireguard"
            configs.mkdir()
            (configs / "bash-created.conf").write_text("PrivateKey = DO-NOT-LEAK")
            (configs / "gui-created.conf").write_text("PrivateKey = ANOTHER-SECRET")
            (configs / "invalid name.conf").write_text("bad")
            (configs / "link.conf").symlink_to(configs / "gui-created.conf")
            destination = root / "native.txt"
            with patch.object(PUBLISHER.os, "geteuid", return_value=0):
                with patch.object(PUBLISHER.os, "fchown"):
                    names = PUBLISHER.publish(configs, destination, reader_gid=os.getgid())
                self.assertEqual(names, ("bash-created", "gui-created"))
                self.assertEqual(destination.read_text(), "bash-created\ngui-created\n")
                self.assertNotIn("DO-NOT-LEAK", destination.read_text())
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o640)
                (configs / "gui-created.conf").unlink()
                with patch.object(PUBLISHER.os, "fchown"):
                    PUBLISHER.publish(configs, destination, reader_gid=os.getgid())
                self.assertEqual(destination.read_text(), "bash-created\n")

    def test_reader_validates_root_owned_snapshot_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "names.txt"
            target.write_text("wg1\nwg0\n")
            # Dell's user umask can yield 0664, rightly rejected as group-writable.
            # Explicitly create a safe root-snapshot permission fixture.
            target.chmod(0o640)
            real_stat = target.stat()
            fake_root_stat = SimpleNamespace(
                st_mode=real_stat.st_mode, st_uid=0, st_size=real_stat.st_size
            )
            with patch("wg_deck.core.system_profiles.os.fstat", return_value=fake_root_stat):
                self.assertEqual(read_native_names(target), ("wg0", "wg1"))
            (root / "link.txt").symlink_to(target)
            self.assertIsNone(read_native_names(root / "link.txt"))
            target.write_text("wg0\n../../bad\n")
            changed = target.stat()
            with patch("wg_deck.core.system_profiles.os.fstat", return_value=SimpleNamespace(
                st_mode=changed.st_mode, st_uid=0, st_size=changed.st_size
            )):
                self.assertIsNone(read_native_names(target))

    def test_reader_group_configuration_is_root_owned_and_private(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "reader-gid"
            target.write_text("1000\n")
            mode = stat.S_IFREG | 0o600
            with patch.object(PUBLISHER.os, "fstat", return_value=SimpleNamespace(
                st_mode=mode, st_uid=0
            )):
                self.assertEqual(PUBLISHER.configured_group(target), 1000)
            target.write_text("not-a-gid\n")
            with patch.object(PUBLISHER.os, "fstat", return_value=SimpleNamespace(
                st_mode=mode, st_uid=0
            )):
                with self.assertRaises(ValueError):
                    PUBLISHER.configured_group(target)

    def test_default_debian_install_exposes_names_to_regular_users_without_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            configs = root / "etc_wireguard"
            configs.mkdir(mode=0o700)
            (configs / "existing-profile.conf").write_text("PrivateKey = SENSITIVE")
            destination = root / "native.txt"
            self.assertEqual(PUBLISHER.configured_group(root / "missing-reader-gid"), 0)
            with patch.object(PUBLISHER.os, "geteuid", return_value=0), patch.object(
                PUBLISHER.os, "fchown"
            ):
                names = PUBLISHER.publish(configs, destination, reader_gid=0)
            self.assertEqual(names, ("existing-profile",))
            self.assertEqual(destination.read_text("ascii"), "existing-profile\\n")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o644)
            self.assertNotIn("SENSITIVE", destination.read_text())

    def test_invalid_explicit_reader_config_never_falls_back_to_public(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            secret = root / "reader-gid"
            secret.write_text("1000\\n")
            (root / "link").symlink_to(secret)
            with self.assertRaises(OSError):
                PUBLISHER.configured_group(root / "link")

    def test_missing_snapshot_does_not_return_fake_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(read_native_names(Path(folder) / "missing.txt"))

    def test_gtk_system_files_never_have_separate_managed_identity(self):
        from wg_deck.ui.window import InventoryWorker
        from wg_deck.core.models import ProfileSnapshot, TunnelState
        from wg_deck.core.discovery import Inventory

        state = Inventory((
            ProfileSnapshot("bash-created", TunnelState.DOWN),
            ProfileSnapshot("gui-created", TunnelState.UP),
            ProfileSnapshot("foreign-interface", TunnelState.UP),
        ), (), "wg test", True)
        snapshots = []
        worker = InventoryWorker()
        worker.signals.finished.connect(snapshots.append)
        with patch("wg_deck.ui.window.read_native_names", return_value=(
            "bash-created", "gui-created"
        )), patch("wg_deck.ui.window.discover", return_value=state) as discover_mock:
            worker.run()
        self.assertEqual(
            [p.name for p in snapshots[0].profiles],
            ["bash-created", "gui-created"],
        )
        self.assertEqual(discover_mock.call_args.kwargs["extra_names"],
                         ("bash-created", "gui-created"))
        self.assertEqual(discover_mock.call_args.kwargs["directories"], ())


if __name__ == "__main__":
    unittest.main()
