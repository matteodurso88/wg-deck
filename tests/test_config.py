"""Configuration inspection is read-only, bounded and hook-aware."""

import unittest

from wg_deck.core.config import inspect_config


class ConfigInspectionTests(unittest.TestCase):
    def test_multi_peer_and_executable_hooks_are_reported(self):
        content = (
            "[Interface]\nAddress = 10.0.0.2/32\nPrivateKey = private-secret\n"
            "PreUp = touch /tmp/do-not-execute\n\n"
            "[Peer]\nPublicKey = public-peer-a\nEndpoint = vpn.example.org:51820\n"
            "[Peer]\nPublicKey = public-peer-b\n"
        )
        value = inspect_config(content)
        self.assertEqual(value.address, "10.0.0.2/32")
        self.assertEqual(value.peer_count, 2)
        self.assertEqual(value.first_peer_key, "public-peer-a")
        self.assertEqual(value.private_key, "private-secret")
        self.assertEqual(value.hooks, ("PreUp",))

    def test_no_exec_and_malformed_input(self):
        self.assertEqual(inspect_config("[Peer]\nAllowedIPs = 0.0.0.0/0").peer_count, 1)
        with self.assertRaises(ValueError):
            inspect_config("\x00 bad")

    def test_no_private_key_in_representation_of_error(self):
        with self.assertRaises(ValueError) as thrown:
            inspect_config("x" * (128 * 1024 + 1) + "secret")
        self.assertNotIn("secret", str(thrown.exception))


if __name__ == "__main__":
    unittest.main()
