"""WG Deck canonical vector identity and matt88.it attribution assets.

The vector files are copied verbatim from matteodurso88/matt88:
public/brand/matt88/logo-{light,dark}.svg (Concept 01G-2).
"""
from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def matt88_logo_pixmap(theme: str, *, width: int = 188, height: int = 48) -> QPixmap:
    """Render the official vector wordmark, preserving its aspect ratio."""
    variant = "dark" if theme == "dark" else "light"
    data = (files("wg_deck") / "assets" / "brand" /
            f"matt88-logo-{variant}.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ValueError("Canonical matt88.it brand asset is invalid.")
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap


def wg_deck_logo_pixmap(theme: str, *, width: int = 184, height: int = 37) -> QPixmap:
    """Render owner-approved Concept 09 as paths-only SVG, no font dependency."""
    variant = "light" if theme == "light" else "dark"
    data = (files("wg_deck") / "assets" / "brand" /
            f"wg-deck-logo-{variant}.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ValueError("WG Deck canonical SVG logo is invalid.")
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap
