"""Theme-aware vector icons (no external icon fonts or image downloads).

Minimal 24×24 outlined strokes inspired by standard desktop symbol language,
not the WireGuard trademark.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "Dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "Profiles": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "Diagnostics": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "Settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
    "new": '<path d="M12 5v14M5 12h14"/>',
    "import": '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    "export": '<path d="M12 21V9m-5 5 5-5 5 5M4 7V3h16v4"/>',
    "trash": '<path d="M4 7h16M10 4h4m-8 3 1 14h10l1-14M10 11v6M14 11v6"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14-5L3 9m0-6v6h6M4 13a8 8 0 0 0 14 5l3-3m0 6v-6h-6"/>',
    "edit": '<path d="m4 20 4.5-1 12-12a2.1 2.1 0 0 0-3-3l-12 12L4 20Z"/>',
    "connect": '<path d="M8 5v14l11-7Z"/>',
    "disconnect": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "back": '<path d="m15 6-6 6 6 6M9 12h12"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9 2 2-3 3 2 2-3 3-2-2-3 3"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
}


def vector_icon(name: str, color: str, size: int = 20) -> QIcon:
    body = PATHS.get(name, PATHS["Profiles"])
    markup = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        f'<g stroke="{QColor(color).name()}" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" fill="none">{body}</g></svg>'
    )
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
