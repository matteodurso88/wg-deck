"""Keypair generation must use wg without privileges or shell."""
from __future__ import annotations

import base64
import subprocess
import unittest
from unittest.mock import patch

from wg_deck.core.keys import generate_keypair, KeyGenerationError


class KeyGenerationTests(unittest.TestCase):
    def test_private_only_on_stdin_to_pubkey_and_never_argv(self):
        private = base64.b64encode(bytes([1] * 32)).decode()
        public = base64.b64encode(bytes([2] * 32)).decode()
        responses = [
            subprocess.CompletedProcess(args=(), returncode=0, stdout=(private + "\n").encode(), stderr=b""),
            subprocess.CompletedProcess(args=(), returncode=0, stdout=(public + "\n").encode(), stderr=b""),
        ]
        with patch("wg_deck.core.keys.shutil.which", return_value="/usr/bin/wg"):
            with patch("wg_deck.core.keys.subprocess.run", side_effect=responses) as proc:
                result = generate_keypair()
        self.assertEqual(result, (private, public))
        self.assertEqual(proc.call_args_list[0].args[0], ("/usr/bin/wg", "genkey"))
        self.assertEqual(proc.call_args_list[1].args[0], ("/usr/bin/wg", "pubkey"))
        self.assertEqual(proc.call_args_list[1].kwargs["input"], (private + "\n").encode())
        self.assertNotIn(private, str(proc.call_args_list[1].args))

    def test_no_wireguard_binary_fails_without_side_effects(self):
        with patch("wg_deck.core.keys.shutil.which", return_value=None):
            with self.assertRaises(KeyGenerationError):
                generate_keypair()


if __name__ == "__main__":
    unittest.main()
