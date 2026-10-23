"""Offline tests for unified authenticated profile inventory, read and export."""

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wg_deck.core.privileged import list_system_profiles, read_profile, execute
from wg_deck.core.profile_copy import export_existing, CopyError


class UniformProfileTests(unittest.TestCase):
    def test_system_profiles_are_not_partitioned_by_origin(self):
        output = b"OK:list\nwg-lab\nwg-system\nwg-system\n"
        with patch("wg_deck.core.privileged.available", return_value=True):
            with patch("wg_deck.core.privileged.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    (), 0, output, b""
                )
                result = list_system_profiles()
        self.assertTrue(result.ok)
        self.assertEqual(result.names, ("wg-lab", "wg-system"))
        self.assertEqual(run.call_args.args[0][-2:], ("list", "all"))

    def test_read_returns_revision_but_never_logs_secret(self):
        raw = "[Interface]\nPrivateKey = super-secret\n"
        with patch("wg_deck.core.privileged.available", return_value=True):
            with patch("wg_deck.core.privileged.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    (), 0, b"OK:read\n" + raw.encode(), b""
                )
                result = read_profile("wg-system")
        self.assertTrue(result.ok)
        self.assertEqual(result.content, raw)
        self.assertEqual(result.revision, hashlib.sha256(raw.encode()).hexdigest())
        self.assertNotIn("super-secret", repr(result))
        self.assertEqual(run.call_args.args[0][-2:], ("read", "wg-system"))

    def test_replace_uses_only_revision_and_config_on_stdin(self):
        raw = "[Interface]\nAddress = 10.0.0.2/32\n"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with patch("wg_deck.core.privileged.available", return_value=True):
            with patch("wg_deck.core.privileged.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess((), 0, b"OK:replaced\n", b"")
                result = execute("replace", "wg-system", raw, digest)
        self.assertTrue(result.ok)
        self.assertNotIn(raw, str(run.call_args.args[0]))
        self.assertEqual(run.call_args.kwargs["input"], digest.encode() + b"\n" + raw.encode())
        self.assertFalse(execute("replace", "wg-system", raw, "bad").ok)
        self.assertFalse(execute("adopt", "wg-system").ok)

    def test_export_is_exclusive_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "wg-system.conf"
            original = "[Interface]\n# keep this comment\nPostUp = echo external\n"
            result = export_existing("wg-system", original, destination, allowed_root=root)
            self.assertEqual(result.read_text(), original)
            self.assertEqual(result.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(CopyError):
                export_existing("wg-system", "replacement", destination, allowed_root=root)
            with self.assertRaises(CopyError):
                export_existing("wg-system", original, root / "wrong.conf", allowed_root=root)


if __name__ == "__main__":
    unittest.main()
