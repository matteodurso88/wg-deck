"""Supported existing config editing preserves all non-edited content."""
import base64
import unittest

from wg_deck.core.profile_export import (
    PeerDraft, ProfileDraft, ProfileValidationError, parse_supported_profile,
)
from wg_deck.core.profile_rewrite import rewrite_supported_config


def key(number):
    return base64.b64encode(bytes([number]*32)).decode("ascii")


class RewriteTests(unittest.TestCase):
    def test_comments_and_multiple_peers_preserved(self):
        original = (
            "# System-created WireGuard config\n"
            "[Interface]\n"
            f"PrivateKey={key(1)}\n"
            "Address = 10.5.0.2/32\n"
            "# DNS managed locally\n"
            "DNS = 1.1.1.1\n"
            "\n[Peer]\n"
            f"PublicKey = {key(2)}\n"
            "AllowedIPs = 192.0.2.0/24\n"
            "# Important peer comment\n"
            "\n[Peer]\n"
            f"PublicKey = {key(3)}\n"
            "AllowedIPs = 198.51.100.0/24\n"
        )
        profile = parse_supported_profile("wglegacy", original)
        edited = ProfileDraft(
            profile.name, "10.5.0.3/32", profile.private_key,
            (PeerDraft(profile.peers[0].public_key, "10.0.0.0/8"),
             profile.peers[1]),
            dns="9.9.9.9",
        )
        actual = rewrite_supported_config("wglegacy", original, edited)
        self.assertIn("# System-created WireGuard config", actual)
        self.assertIn("# DNS managed locally", actual)
        self.assertIn("# Important peer comment", actual)
        self.assertIn("Address = 10.5.0.3/32", actual)
        self.assertEqual(parse_supported_profile("wglegacy", actual).peers, edited.peers)

    def test_complex_unsupported_configs_are_never_reserialized(self):
        raw = "[Interface]\n" + f"PrivateKey = {key(1)}\nAddress=10.0.0.2/32\nPreUp=echo hello\n"
        draft = ProfileDraft("wglegacy", "10.0.0.2/32", key(1),
                             (PeerDraft(key(2), "0.0.0.0/0"),))
        with self.assertRaises(ProfileValidationError):
            rewrite_supported_config("wglegacy", raw, draft)

    def test_append_peer_and_reject_rename(self):
        raw = (
            f"[Interface]\nPrivateKey = {key(1)}\nAddress = 10.2.2.2/32\n\n"
            f"[Peer]\nPublicKey = {key(2)}\nAllowedIPs = 192.0.2.0/24\n"
        )
        first = parse_supported_profile("wglegacy", raw)
        next_value = ProfileDraft(
            "wglegacy", first.address, first.private_key,
            first.peers + (PeerDraft(key(3), "198.51.100.0/24"),),
        )
        updated = rewrite_supported_config("wglegacy", raw, next_value)
        self.assertEqual(updated.count("[Peer]"), 2)
        self.assertEqual(parse_supported_profile("wglegacy", updated).peers, next_value.peers)
        with self.assertRaises(ProfileValidationError):
            rewrite_supported_config("wglegacy", raw, ProfileDraft(
                "different", first.address, first.private_key, first.peers
            ))


if __name__ == "__main__":
    unittest.main()
