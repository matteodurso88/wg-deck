"""Strict supported-format imports must not discard unknown or unsafe options."""

from __future__ import annotations

import base64
import unittest

from wg_deck.core.profile_export import (
    PeerDraft, ProfileDraft, render_new_profile, parse_supported_profile,
    ProfileValidationError,
)


def key(n: int):
    return base64.b64encode(bytes([n] * 32)).decode()


class ImportedProfileTests(unittest.TestCase):
    def test_two_peers_roundtrip(self):
        draft = ProfileDraft(
            "wgtest", "10.0.0.4/32", key(1),
            (PeerDraft(key(2), "0.0.0.0/0", "vpn.example.org:51820"),
             PeerDraft(key(3), "192.168.3.0/24")),
        )
        source = render_new_profile(draft)
        self.assertEqual(parse_supported_profile(draft.name, source), draft)

    def test_unknown_option_is_never_discarded(self):
        cfg = f"[Interface]\nPrivateKey = {key(1)}\nAddress = 10.0.0.2/32\nSaveConfig = true\n\n"
        cfg += f"[Peer]\nPublicKey = {key(2)}\nAllowedIPs = 0.0.0.0/0\n"
        with self.assertRaises(ProfileValidationError):
            parse_supported_profile("wgtest", cfg)


if __name__ == "__main__":
    unittest.main()
