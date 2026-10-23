"""Exercise a one-theme demo screenshot suite without touching VPN state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class DemoCaptureSuiteTests(unittest.TestCase):
    def test_compact_light_suite_has_complete_manifest_and_valid_archive(self):
        with tempfile.TemporaryDirectory(prefix="wgdeck-demo-qa-") as temporary:
            target = Path(temporary) / "screenshots"
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["QT_SCALE_FACTOR"] = "1"
            env.pop("PYTHONPATH", None)
            command = [
                sys.executable, str(ROOT / "scripts" / "capture_demo_suite.py"),
                "--themes", "light", "--layouts", "compact",
                "--output", str(target),
            ]
            completed = subprocess.run(
                command, cwd=ROOT, env=env,
                capture_output=True, text=True, timeout=100, check=False,
            )
            self.assertEqual(
                completed.returncode, 0,
                completed.stdout + "\n" + completed.stderr,
            )
            manifest = json.loads((target / "manifest.json").read_text("utf-8"))
            expected = [
                "dashboard", "profiles", "profile-editor",
                "profile-editor-bottom", "diagnostics", "settings", "tray-menu",
            ]
            self.assertEqual(manifest["count"], len(expected))
            self.assertEqual(manifest["scenes"], expected)
            self.assertEqual(manifest["themes"], ["light"])
            self.assertEqual(len(manifest["screenshots"]), 7)
            self.assertTrue(all(item["synthetic_demo"] for item in manifest["screenshots"]))
            self.assertEqual(
                {item["scene"] for item in manifest["screenshots"]}, set(expected)
            )
            for item in manifest["screenshots"]:
                screenshot = target / item["file"]
                self.assertTrue(screenshot.is_file(), item)
                self.assertEqual(screenshot.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                self.assertGreater(item["width"], 0)
                self.assertGreater(item["height"], 0)
            self.assertTrue((target / "contact-compact.png").is_file())
            with ZipFile(target / "wg-deck-demo-suite.zip") as archive:
                self.assertIsNone(archive.testzip())
                files = set(archive.namelist())
                self.assertIn("manifest.json", files)
                self.assertIn("contact-compact.png", files)
                self.assertEqual(
                    sum(p.startswith("screens/compact/") for p in files), 7
                )


if __name__ == "__main__":
    unittest.main()
