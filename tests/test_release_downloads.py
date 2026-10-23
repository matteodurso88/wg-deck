"""Offline regression for GitHub Release aggregate download summary."""
import importlib.util
from pathlib import Path
import unittest

module_path = Path(__file__).resolve().parents[1] / "scripts" / "release_downloads.py"
spec = importlib.util.spec_from_file_location("release_downloads", module_path)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DownloadStatsTests(unittest.TestCase):
    def test_draft_not_counted_and_uploaded_assets_summed(self):
        fixture = [
            {"draft": True, "tag_name": "v2", "assets": [{"name": "private", "download_count": 50}]},
            {
                "draft": False, "tag_name": "v1.0.0", "published_at": "2026-10-23T23:00:00Z",
                "assets": [
                    {"name": "wg_deck-1.0.0-py3-none-any.whl", "download_count": 17},
                    {"name": "wg_deck-1.0.0.tar.gz", "download_count": 3},
                ],
            },
        ]
        stats = module.summarize(fixture)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["tag"], "v1.0.0")
        self.assertEqual(stats[0]["total_uploaded_asset_downloads"], 20)
        self.assertEqual([a["downloads"] for a in stats[0]["assets"]], [17, 3])


if __name__ == "__main__":
    unittest.main()
