"""Launch the canonical red-accent Qt shell.

No privileged WireGuard operation is performed from this process.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .ui.window import MainWindow

    parser = argparse.ArgumentParser(description="WG Deck (Linux VPN profile manager)")
    parser.add_argument("--demo", action="store_true", help="Use clearly labeled synthetic profiles; no discovery")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    app = QApplication([sys.argv[0]])
    app.setApplicationName("WG Deck")
    app.setOrganizationName("matt88.it")
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow(demo=args.demo)
    window.show()
    return app.exec()
