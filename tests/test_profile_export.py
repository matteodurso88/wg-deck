"""Unprivileged, offline validation and safe-write regression suite."""

from __future__ import annotations

import base64
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wg_deck.core.profile_export import (
    PeerDraft,
    ProfileDraft,
    ProfileValidationError,
    export_new_profile,
    render_new_profile,
)


def key(number: int) -> str:
    return base64.b64encode(bytes([number] * 32)).decode("ascii")


def sample(*, name: str = "wglab") -> ProfileDraft:
    return ProfileDraft(
        name=name,
        address="10.8.0.2/32, fd00::2/128",
        private_key=key(1),
        dns="1.1.1.1, 2606:4700:4700::1111",
        listen_port=51820,
        mtu=1420,
        peers=(
            PeerDraft(key(2), "0.0.0.0/0, ::/0", "vpn.example.org:51820", key(3), 25),
            PeerDraft(key(4), "192.0.2.0/24", "[2001:db8::1]:51820"),
        ),
    )


class RenderTests(unittest.TestCase):
    def test_two_peers_valid_serialization_without_hooks(self):
        content = render_new_profile(sample())
        self.assertEqual(content.count("[Peer]"), 2)
        self.assertIn("DNS = 1.1.1.1, 2606:4700:4700::1111", content)
        self.assertIn("AllowedIPs = 0.0.0.0/0, ::/0", content)
        self.assertIn("Endpoint = [2001:db8::1]:51820", content)
        for forbidden in ("PreUp", "PostUp", "PreDown", "PostDown"):
            self.assertNotIn(forbidden, content)

    def test_reject_invalid_field_injection_and_key(self):
        valid = sample()
        changes = (
            {"name": "../../escape"},
            {"name": "1234567890123456"},
            {"address": "10.8.0.2/32\nPostUp = evil"},
            {"private_key": "not-a-wireguard-key"},
            {"dns": "8.8.8.8\nPostDown = bad"},
            {"mtu": 300},
            {"peers": ()},
            {"peers": (PeerDraft(key(2), "0.0.0.0/0", "vpn.example.org:51820\nPostUp = bad"),)},
            {"peers": (PeerDraft(key(2), "10.0.0.0/8\nPostUp = bad"),)},
            {"peers": (PeerDraft("invalid", "0.0.0.0/0"),)},
        )
        for change in changes:
            fields = {name: getattr(valid, name) for name in valid.__dataclass_fields__}
            fields.update(change)
            with self.subTest(change=list(change)), self.assertRaises(ProfileValidationError):
                render_new_profile(ProfileDraft(**fields))

    def test_secret_not_exposed_in_representation_or_validation_error(self):
        profile = sample()
        self.assertNotIn(profile.private_key, repr(profile))
        self.assertNotIn(profile.peers[0].preshared_key, repr(profile))
        with self.assertRaises(ProfileValidationError) as ex:
            render_new_profile(ProfileDraft("wglab", "10.0.0.2/32", key(1), (PeerDraft("SECRET!", "0.0.0.0/0"),)))
        self.assertNotIn("SECRET!", str(ex.exception))


class SecureExportTests(unittest.TestCase):
    def test_export_is_exclusive_and_mode_is_0600(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "wglab.conf"
            with patch("wg_deck.core.profile_export.os.geteuid", return_value=1000):
                self.assertEqual(export_new_profile(sample(), target, allowed_root=root), target)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(target.read_text().count("[Peer]"), 2)
                with self.assertRaises(ProfileValidationError):
                    export_new_profile(sample(), target, allowed_root=root)
            self.assertEqual(target.read_text().count("[Peer]"), 2)

    def test_symlink_and_traversal_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            outside_path = Path(outside)
            (root / "jump").symlink_to(outside_path, target_is_directory=True)
            (root / "wglab.conf").symlink_to(outside_path / "other.conf")
            with patch("wg_deck.core.profile_export.os.geteuid", return_value=1000):
                for candidate in (root / "jump/wglab.conf", root / "wglab.conf", outside_path / "wglab.conf"):
                    with self.subTest(candidate=candidate), self.assertRaises(ProfileValidationError):
                        export_new_profile(sample(), candidate, allowed_root=root)

    def test_export_is_never_performed_as_root(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "wglab.conf"
            with patch("wg_deck.core.profile_export.os.geteuid", return_value=0):
                with self.assertRaises(ProfileValidationError):
                    export_new_profile(sample(), target, allowed_root=Path(temp))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
