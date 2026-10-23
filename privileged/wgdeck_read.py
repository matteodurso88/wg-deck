#!/usr/bin/python3
"""Restricted Polkit entrypoint for viewing/exporting native WireGuard configs.

Short-lived Polkit authorization is available ONLY for read/bundle, not for
create/delete/replace or connect/disconnect. Secrets are never cached by the UI.
"""
from __future__ import annotations

import os
import re
import sys

ROOT_HELPER = "/usr/local/libexec/wg-deck-helper"
INTERFACE = re.compile(r"[A-Za-z0-9_=+.-]{1,15}\Z")


def main() -> int:
    if os.geteuid() != 0 or len(sys.argv) != 3:
        return 2
    action, name = sys.argv[1:]
    if action == "bundle":
        if name != "all":
            return 2
    elif action == "read":
        if name in {".", ".."} or not INTERFACE.fullmatch(name):
            return 2
    else:
        return 2
    os.execv(ROOT_HELPER, (ROOT_HELPER, action, name))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
