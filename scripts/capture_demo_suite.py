"""Generate an auditable visual QA bundle of synthetic WG Deck demo screens.

Default matrix: 7 scenes x 2 themes x 2 viewport sizes = 28 PNGs.
Also creates two legible contact sheets, a manifest and a single ZIP.
No network/VPN operations; outputs are never staged in Git.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QImage, QImageReader, QPainter
from PySide6.QtWidgets import QApplication

from capture_ui import EXTENDED_PAGES, capture

ROOT = Path(__file__).resolve().parents[1]
TILE_WIDTH = 605
TILE_HEIGHT = 448
HEADER_HEIGHT = 38
GAP = 15
MARGIN = 26


def _commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, timeout=5, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _image_size(path: Path) -> tuple[int, int]:
    reader = QImageReader(str(path))
    dims = reader.size()
    if not dims.isValid():
        raise RuntimeError(f"Invalid PNG: {path}")
    return (dims.width(), dims.height())


def _contact_sheet(
    output: Path, screenshots: dict[tuple[str, str, str], Path],
    layout: str, themes: tuple[str, ...],
) -> Path:
    columns, rows = len(themes), len(EXTENDED_PAGES)
    width = MARGIN * 2 + columns * TILE_WIDTH + (columns - 1) * GAP
    height = MARGIN * 2 + rows * TILE_HEIGHT + (rows - 1) * GAP
    sheet = QImage(width, height, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#141A22"))
    painter = QPainter(sheet)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(QFont("Sans Serif", 11))
        for row, page in enumerate(EXTENDED_PAGES):
            for column, theme in enumerate(themes):
                x = MARGIN + column * (TILE_WIDTH + GAP)
                y = MARGIN + row * (TILE_HEIGHT + GAP)
                painter.fillRect(x, y, TILE_WIDTH, TILE_HEIGHT, QColor("#202A36"))
                painter.setPen(QColor("#F3F6FB"))
                painter.drawText(
                    x + 14, y + 26,
                    f"{page.replace('-', ' ').title()}   ·   {theme.title()}   ·   {layout.title()}"
                )
                source_path = screenshots[(layout, theme, page)]
                image = QImage(str(source_path))
                if image.isNull():
                    raise RuntimeError(f"Unable to load screenshot: {source_path}")
                scaled = image.scaled(
                    TILE_WIDTH - 24, TILE_HEIGHT - HEADER_HEIGHT - 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                px = x + (TILE_WIDTH - scaled.width()) // 2
                py = y + HEADER_HEIGHT + (TILE_HEIGHT - HEADER_HEIGHT - scaled.height()) // 2
                painter.drawImage(QPoint(px, py), scaled)
    finally:
        painter.end()
    target = output / f"contact-{layout}.png"
    if not sheet.save(str(target), "PNG"):
        raise RuntimeError(f"Could not save {target}")
    return target


def build_suite(
    output: Path, *, themes: tuple[str, ...] = ("light", "dark"),
    layouts: tuple[str, ...] = ("desktop", "compact"),
) -> dict:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite an existing QA directory: {output}")
    output.mkdir(parents=True, mode=0o700)
    shots: dict[tuple[str, str, str], Path] = {}
    manifest_items: list[dict] = []
    try:
        # Force QApplication initialization before rendering contact sheets.
        app = QApplication.instance() or QApplication([])
        if app is None:
            raise RuntimeError("QApplication initialization failed")
        for layout in layouts:
            compact = layout == "compact"
            screen_dir = output / "screens" / layout
            generated = capture(
                screen_dir, themes=themes, compact=compact,
                extended=True, prefix="wg-deck"
            )
            for theme in themes:
                for page in EXTENDED_PAGES:
                    suffix = "-compact" if compact else ""
                    path = screen_dir / f"wg-deck-{theme}-{page}{suffix}.png"
                    if path not in generated:
                        raise RuntimeError(f"Missing expected screenshot: {path}")
                    width, height = _image_size(path)
                    shots[(layout, theme, page)] = path
                    manifest_items.append({
                        "file": path.relative_to(output).as_posix(),
                        "layout": layout, "theme": theme, "scene": page,
                        "width": width, "height": height,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "synthetic_demo": True,
                    })
        expected = len(themes) * len(layouts) * len(EXTENDED_PAGES)
        if len(manifest_items) != expected:
            raise RuntimeError(f"Expected {expected} captures, got {len(manifest_items)}")
        sheets = [_contact_sheet(output, shots, layout, themes) for layout in layouts]
        manifest = {
            "product": "WG Deck",
            "version": "1.0.0",
            "mode": "demo",
            "data": "synthetic only — no VPN actions or secrets",
            "tray": "Qt menu preview; NOT a GNOME tray screenshot",
            "source_commit": _commit(),
            "themes": list(themes),
            "layouts": {"desktop": [1400, 920], "compact": [1000, 720]},
            "scenes": list(EXTENDED_PAGES),
            "count": expected,
            "screenshots": manifest_items,
            "contact_sheets": [p.name for p in sheets],
        }
        meta = output / "manifest.json"
        meta.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )
        readme = output / "READ_ME.txt"
        readme.write_text(
            "WG Deck v1.0.0 — synthetic DEMO visual QA bundle\n"
            "Captured with Qt offscreen. Nothing in this archive is a real VPN profile.\n"
            "The tray-menu image is an offscreen Qt menu preview, not a GNOME tray.\n"
            "Review every original PNG at 100% and compare desktop vs compact, Light vs Dark.\n"
            "The manifest records layout, theme, scene, resolution and SHA-256.\n"
            "No WireGuard keys, configuration files, machine hostnames or IPs were read.\n",
            encoding="utf-8"
        )
        bundle = output / "wg-deck-demo-suite.zip"
        with ZipFile(bundle, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in [meta, readme, *sheets, *shots.values()]:
                archive.write(path, arcname=path.relative_to(output).as_posix())
        with ZipFile(bundle) as archive:
            damaged = archive.testzip()
            if damaged is not None:
                raise RuntimeError(f"ZIP integrity failed: {damaged}")
        print(f"WG Deck DEMO suite: {expected} PNG captures")
        print(f"Contact sheets: {len(sheets)}")
        print(f"Source commit: {manifest['source_commit'] or 'unknown'}")
        print(f"Directory: {output}")
        print(f"ZIP: {bundle}")
        print("No VPN operations; all profiles displayed are synthetic demo data.")
        return manifest
    except Exception:
        # Keep any partial captures for inspection, but never claim PASS.
        print(f"INCOMPLETE suite; partial outputs preserved at: {output}")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="WG Deck complete demo screenshot suite")
    parser.add_argument("--output", type=Path, default=None,
                        help="Fresh output folder (defaults to ignored local/demo-suite/<UTC timestamp>)")
    parser.add_argument("--themes", choices=("both", "light", "dark"), default="both")
    parser.add_argument("--layouts", choices=("both", "desktop", "compact"), default="both")
    args = parser.parse_args()
    output = args.output or (
        ROOT / "local" / "demo-suite" /
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    themes = ("light", "dark") if args.themes == "both" else (args.themes,)
    layouts = ("desktop", "compact") if args.layouts == "both" else (args.layouts,)
    build_suite(output, themes=themes, layouts=layouts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
