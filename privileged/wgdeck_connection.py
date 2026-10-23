#!/usr/bin/python3
"""Root-owned Polkit entrypoint for the limited WireGuard toggle action.

Both connect/disconnect share ONE auth_admin_keep authorization. Nothing is
executed from user-owned paths, no shells or arbitrary command arguments.
Delegate to the existing audited, root-installed helper for all checks.
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
    if action not in {"up", "down"} or name in {".", ".."} or not INTERFACE.fullmatch(name):
        return 2
    # No user-supplied executable, config path, environment, or command string.
    # execv replaces this process and preserves the policy-authorized UID.
    os.execv(ROOT_HELPER, (ROOT_HELPER, action, name))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
