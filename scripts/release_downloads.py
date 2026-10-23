#!/usr/bin/env python3
"""Read aggregate GitHub Release asset download counts; no tracking cookies.

Only explicitly uploaded release assets have these GitHub counters.
This is NOT an installation, visitor or unique-user counter.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_REPOSITORY = "matteodurso88/wg-deck"
API_ROOT = "https://api.github.com"


def load_releases(repository: str, max_pages: int = 5) -> list[dict]:
    if not repository or "/" not in repository or repository.count("/") != 1:
        raise ValueError("Expected a GitHub owner/repository name.")
    releases: list[dict] = []
    for page in range(1, max_pages + 1):
        query = urlencode({"per_page": 100, "page": page})
        url = f"{API_ROOT}/repos/{repository}/releases?{query}"
        request = Request(
            url, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "wg-deck-release-stats",
            },
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        if not isinstance(result, list):
            raise ValueError("Unexpected GitHub Releases API response.")
        releases.extend(result)
        if len(result) < 100:
            break
    return releases


def summarize(releases: list[dict]) -> list[dict]:
    result = []
    for release in releases:
        if release.get("draft", False):
            continue
        assets = [
            {"name": asset["name"], "downloads": int(asset.get("download_count", 0))}
            for asset in release.get("assets", [])
            if isinstance(asset, dict) and "name" in asset
        ]
        result.append({
            "tag": release.get("tag_name", "unknown"),
            "published_at": release.get("published_at"),
            "assets": assets,
            "total_uploaded_asset_downloads": sum(a["downloads"] for a in assets),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print aggregate GitHub Release asset downloads (not unique users)."
    )
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = summarize(load_releases(args.repository))
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(f'{row["tag"]}: {row["total_uploaded_asset_downloads"]} asset downloads')
            for asset in row["assets"]:
                print(f'  {asset["name"]}: {asset["downloads"]}')
        if not rows:
            print("No published releases found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
