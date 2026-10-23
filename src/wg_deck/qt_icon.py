"""Canonical WG Deck app/tray icon derived from owner-approved Concept 09.

No shield or third-party WireGuard brand asset is used.
"""
from __future__ import annotations

from importlib.resources import files


def make_app_icon():
    """Render packaged vectors at multiple sizes for GNOME and the system tray."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    data = (files("wg_deck") / "assets" / "brand" /
            "wg-deck-app.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        raise ValueError("WG Deck packaged app SVG is invalid.")

    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            renderer.render(painter)
        finally:
            painter.end()
        icon.addPixmap(pixmap)
    return icon
