"""Pure standard-library tests requiring a real installed editable package."""

import unittest
import tomllib
from pathlib import Path
from importlib.metadata import version

from wg_deck import __version__
from wg_deck.core.models import ProfileSnapshot, TunnelState


class FoundationTests(unittest.TestCase):
    def test_product_version_target(self):
        self.assertEqual(__version__, "1.0.0")

    def test_pep639_license_metadata(self):
        metadata_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with metadata_path.open("rb") as source:
            project = tomllib.load(source)["project"]
        self.assertEqual(project["license"], "GPL-3.0-or-later")
        self.assertFalse(any(
            item.startswith("License ::") for item in project.get("classifiers", [])
        ), "PEP 639 SPDX license must not be combined with deprecated classifiers")

    def test_distribution_is_installed(self):
        self.assertEqual(version("wg-deck"), __version__)

    def test_profile_starts_without_claiming_connectivity(self):
        profile = ProfileSnapshot(name="lab")
        self.assertEqual(profile.state, TunnelState.UNKNOWN)
        self.assertIsNone(profile.last_handshake)
        self.assertEqual(profile.rx_bytes, 0)
        self.assertEqual(profile.tx_bytes, 0)


if __name__ == "__main__":
    unittest.main()
