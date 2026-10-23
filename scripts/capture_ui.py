"""Isolated WG Deck DEMO screenshots for visual regression review.

Purely synthetic demo inventory. No root helpers, VPN state changes or access
to user WireGuard configurations. Output remains under git-ignored local/.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

# Set before importing Qt, enabling unattended capture on Dell Ubuntu.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from wg_deck.ui.theme import ThemeMode
from wg_deck.ui.window import MainWindow

PAGES = ("dashboard", "profiles", "profile-editor", "diagnostics", "settings")
EXTENDED_PAGES = (
    "dashboard",
    "profiles",
    "profile-editor",
    "profile-editor-bottom",
    "diagnostics",
    "settings",
    "tray-menu",
)
PAGE_INDEX = {"dashboard": 0, "profiles": 1, "diagnostics": 2, "settings": 3}


def _grab_scene(window: MainWindow, app: QApplication, page: str):
    if page == "tray-menu":
        # Qt-only menu preview. No actual GNOME shell/tray integration is used.
        original_tray, original_menu = window.tray, getattr(window, "menu", None)
        tray = QSystemTrayIcon(window.windowIcon(), window)
        menu = QMenu(window)
        try:
            window.tray, window.menu = tray, menu
            window.refresh_tray()
            if not menu.actions() or menu.actions()[0].text() != "WG Deck":
                raise RuntimeError("DEMO tray menu is missing the canonical WG Deck title")
            menu.resize(menu.sizeHint())
            menu.show()
            app.processEvents()
            screenshot = menu.grab()
            return screenshot
        finally:
            menu.hide()
            window.tray, window.menu = original_tray, original_menu
            menu.deleteLater()
            tray.deleteLater()

    if page in ("profile-editor", "profile-editor-bottom"):
        window.new_profile()  # resets a synthetic in-memory draft only
        app.processEvents()
        editor = window.profiles_stack.currentWidget()
        scrollbar = editor.verticalScrollBar()
        scrollbar.setValue(
            scrollbar.maximum() if page == "profile-editor-bottom" else 0
        )
    else:
        window.go(PAGE_INDEX[page])
    app.processEvents()
    return window.grab()


def capture(
    output: Path, *, themes: tuple[str, ...], compact: bool = False,
    extended: bool = False, prefix: str = "wgm",
) -> list[Path]:
    """Capture a fully isolated demo matrix, preserving caller environment."""
    original_config_home = os.environ.get("XDG_CONFIG_HOME")
    exported: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix="wg-deck-demo-config-") as config_root:
            os.environ["XDG_CONFIG_HOME"] = config_root
            app = QApplication.instance() or QApplication([])
            window = MainWindow(demo=True)
            try:
                window.timer.stop()  # stable synthetic counters while capturing
                window.resize(1000, 720) if compact else window.resize(1400, 920)
                window.show()
                app.processEvents()
                output.mkdir(parents=True, exist_ok=True)
                pages = EXTENDED_PAGES if extended else PAGES
                for mode in themes:
                    window.theme.set_mode(ThemeMode(mode))
                    app.processEvents()
                    for page in pages:
                        pixmap = _grab_scene(window, app, page)
                        if pixmap.isNull():
                            raise RuntimeError(f"Qt returned a null capture for {mode}/{page}")
                        suffix = "-compact" if compact else ""
                        target = output / f"{prefix}-{mode}-{page}{suffix}.png"
                        if target.exists():
                            raise FileExistsError(f"Refusing to overwrite {target}")
                        if not pixmap.save(str(target), "PNG"):
                            raise RuntimeError(f"Cannot save {target}")
                        exported.append(target)
            finally:
                window.close()
                app.processEvents()
    finally:
        if original_config_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = original_config_home
    return exported


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture WG Deck demo screenshots")
    parser.add_argument("--theme", choices=("light", "dark", "all"), default="all")
    parser.add_argument("--compact", action="store_true",
                        help="Capture a 1000x720 compact-layout QA set")
    parser.add_argument("--extended", action="store_true",
                        help="Include editor bottom and Qt tray-menu preview")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    modes = ("light", "dark") if args.theme == "all" else (args.theme,)
    result = capture(
        root / "local" / "ui-fidelity", themes=modes, compact=args.compact,
        extended=args.extended,
    )
    for path in result:
        print(f"Captured {path.relative_to(root)}")
    print("Demo only: review captures visually; GNOME tray/Wayland requires real QA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
