"""Export an authorized system profile to a NEW user-owned file safely.

Never overwrite, follow symlink targets, or print private keys in diagnostics.
"""
from __future__ import annotations

import os
from pathlib import Path

from .discovery import valid_interface


class CopyError(ValueError):
    pass


def export_existing(name: str, content: str, destination: Path,
                    allowed_root: Path | None = None) -> Path:
    if not valid_interface(name):
        raise CopyError("Invalid profile name.")
    if len(content.encode("utf-8")) > 64 * 1024:
        raise CopyError("Profile is too large to export.")
    path = Path(destination)
    root = (allowed_root or Path.home()).resolve()
    if path.name != f"{name}.conf":
        raise CopyError("Export filename must match the profile.")
    parent = path.parent.resolve(strict=True)
    if not parent.is_relative_to(root):
        raise CopyError("Export only into a directory under your home.")
    target = parent / path.name
    try:
        fd = os.open(
            target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
    except FileExistsError:
        raise CopyError("The destination already exists; export never overwrites.") from None
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content.encode("utf-8"))
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise CopyError("Unable to export the profile.") from None
    return target
