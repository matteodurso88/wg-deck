"""Offline v1 privileged contract tests: no root execution or VPN commands."""

from __future__ import annotations

import base64
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from wg_deck.core.privileged import execute, OperationResult
from wg_deck.core.profile_export import (
    ProfileDraft, PeerDraft, render_new_profile, parse_supported_profile,
    ProfileValidationError,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "privileged" / "wgdeck_helper.py"
spec = importlib.util.spec_from_file_location("wgdeck_helper_test", SOURCE)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def key(number):
    return base64.b64encode(bytes([number] * 32)).decode()


def profile():
    return ProfileDraft(
        name="wgv1test", private_key=key(1), address="10.10.9.2/32",
        peers=(PeerDraft(key(2), "0.0.0.0/0", "vpn.example.org:51820"),
               PeerDraft(key(3), "192.0.2.0/24", "[2001:db8::1]:51820")),
    )


class OfflineHelperContract(unittest.TestCase):
    def test_valid_generated_multi_peer_configuration(self):
        data = render_new_profile(profile())
        helper.valid_config(data.encode())
        imported = parse_supported_profile("wgv1test", data)
        self.assertEqual(imported, profile())

    def test_rejects_hooks_unknown_and_missing_fields(self):
        generated = render_new_profile(profile())
        variants = (
            generated.replace("[Peer]", "PreUp = touch /tmp/untrusted\n[Peer]", 1),
            generated.replace("[Peer]", "Table = off\n[Peer]", 1),
            generated.replace("PublicKey =", "PostDown = echo hi\nPublicKey =", 1),
            generated.replace("PrivateKey =", "ListenPort = 99999\nPrivateKey =", 1),
            generated.replace("AllowedIPs = 0.0.0.0/0\n", ""),
            generated.replace("PublicKey =", "OtherKey =", 1),
            generated.replace("Address =", "Address = 10.0.0.3/32\nAddress =", 1),
        )
        for variant in variants:
            with self.subTest(variant=variant[:45]), self.assertRaises(helper.Rejected):
                helper.valid_config(variant.encode())
        with self.assertRaises(ProfileValidationError):
            parse_supported_profile("wgv1test", generated.replace("[Peer]", "PostUp = whoami\n[Peer]", 1))

    def test_rejects_invalid_ids(self):
        for bad in ("../x", "x" * 16, "/etc/passwd", "name with spaces", ".."):
            with self.assertRaises(helper.Rejected):
                helper.safe_name(bad)

    def test_non_root_never_executes_wireguard(self):
        with patch.object(helper.os, "geteuid", return_value=1000):
            with self.assertRaises(helper.Rejected):
                helper.handle("up", "wgv1test")

    def test_existing_and_new_profiles_share_same_up_down_permissions(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / ".runtime"
            runtime.mkdir()
            data = render_new_profile(profile()).encode()
            (root / "wgv1test.conf").write_bytes(data)
            # No ownership marker or special adoption stage.
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", runtime),
                patch.object(helper, "secure_directory"),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "secure_file", return_value=data),
                patch.object(helper, "systemd_is", return_value=False),
                patch.object(helper, "run") as run,
            ):
                with patch.object(helper, "is_up", side_effect=[False, True]):
                    helper.handle("up", "wgv1test")
                    run.assert_called_with("/usr/bin/wg-quick", "up", "wgv1test")
                with patch.object(helper, "is_up", side_effect=[True, False]):
                    with patch.object(helper, "is_wireguard", return_value=True):
                        helper.handle("down", "wgv1test")
                        run.assert_called_with("/usr/bin/wg-quick", "down", "wgv1test")
                with patch.object(helper, "is_up", return_value=True):
                    with self.assertRaises(helper.Rejected):
                        helper.handle("up", "wgv1test")
                with patch.object(helper, "is_up", side_effect=[False, True]):
                    with patch.object(helper, "systemd_is", return_value=True):
                        helper.handle("up", "wgv1test")
                        run.assert_called_with(
                            "/usr/bin/systemctl", "start", "wg-quick@wgv1test.service"
                        )

                with patch.object(helper, "is_up", return_value=True):
                    with patch.object(helper, "is_wireguard", return_value=False):
                        with self.assertRaises(helper.Rejected):
                            helper.handle("down", "wgv1test")


    def test_root_helper_exclusive_install_and_revision_protected_edit(self):
        from tempfile import TemporaryDirectory
        import hashlib
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / ".runtime"
            runtime.mkdir()
            content = render_new_profile(profile()).encode("utf-8")
            # simulate root-only stat for test fixture through fixed return mock
            def secure_file(path):
                return Path(path).read_bytes()
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", runtime),
                patch.object(helper, "secure_directory", side_effect=lambda p: p.mkdir(exist_ok=True)),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "secure_file", side_effect=secure_file),
                patch.object(helper, "is_up", return_value=False),
            ):
                helper.handle("install", "wgv1test", content)
                target = root / "wgv1test.conf"
                self.assertEqual(target.read_bytes(), content)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(helper.Rejected):
                    helper.handle("install", "wgv1test", content)
                before = hashlib.sha256(content).hexdigest().encode("ascii")
                with self.assertRaises(helper.Rejected):
                    helper.handle("replace", "wgv1test", b"0"*64 + b"\n" + content)
                helper.handle("replace", "wgv1test", before + b"\n" + content)
                self.assertEqual(target.read_bytes(), content)
                backup_dir = root / ".wg-deck-backups"
                self.assertEqual(len(list(backup_dir.glob("*.conf"))), 1)
                with patch.object(helper, "is_up", return_value=True):
                    with self.assertRaises(helper.Rejected):
                        helper.handle("replace", "wgv1test", before + b"\n" + content)

    def test_unsupported_existing_config_can_be_read_without_rewriting(self):
        from tempfile import TemporaryDirectory
        import io
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / ".runtime"
            runtime.mkdir()
            unsupported = b"[Interface]\nPreUp = iptables -A TEST\n"
            (root / "legacy.conf").write_bytes(unsupported)
            with (
                patch.object(helper, "ROOT", root),
                patch.object(helper, "RUNTIME", runtime),
                patch.object(helper, "secure_directory"),
                patch.object(helper.os, "geteuid", return_value=0),
                patch.object(helper, "secure_file", return_value=unsupported),
            ):
                sink = io.BytesIO()
                with patch.object(helper.sys, "stdout", type("Out", (), {"buffer": sink})()):
                    helper.handle("read", "legacy")
                self.assertEqual(sink.getvalue(), b"OK:read\n" + unsupported)
                with self.assertRaises(helper.Rejected):
                    helper.handle("replace", "legacy", b"0"*64 + b"\n" + unsupported)

    def test_gui_bridge_never_passes_secrets_on_argv(self):
        config = render_new_profile(profile())
        with patch("wg_deck.core.privileged.available", return_value=True):
            with patch("wg_deck.core.privileged.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    args=(), returncode=0, stdout=b"OK:installed\n", stderr=b""
                )
                result = execute("install", "wgv1test", config)
        self.assertTrue(result.ok)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], ("pkexec", "/usr/local/libexec/wg-deck-helper", "install"))
        self.assertEqual(args[0][3], "wgv1test")
        self.assertEqual(kwargs["input"], config.encode())
        self.assertNotIn(profile().private_key, str(args[0]))
        self.assertFalse(kwargs["check"])
        self.assertFalse(execute("shutdown", "wgv1test").ok)
        self.assertFalse(execute("up", "../../unsafe").ok)


if __name__ == "__main__":
    unittest.main()
