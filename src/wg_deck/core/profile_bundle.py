"""Secure native-profile ZIP backup for use in the unprivileged GUI.

Polkit performs all reads/writes of /etc/wireguard. A ZIP is a secret-bearing
backup: mode 0600, HOME only, exclusive creation, no temporary plaintext files.
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from .discovery import valid_interface
from .profile_export import parse_supported_profile, ProfileValidationError

MAX_BUNDLE = 2 * 1024 * 1024


class BundleError(ValueError):
    """A redacted, user-facing archive validation error."""


def preview_bundle(data: bytes) -> tuple[str, ...]:
    if not data or len(data) > MAX_BUNDLE:
        raise BundleError("The archive is empty or exceeds 2 MiB.")
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 100:
                raise BundleError("Archive must contain 1–100 native profiles.")
            found: set[str] = set()
            total = 0
            for entry in entries:
                if (not entry.filename.endswith(".conf")
                        or entry.filename != Path(entry.filename).name
                        or not valid_interface(entry.filename[:-5])
                        or entry.filename in found or entry.is_dir()
                        or entry.compress_type != zipfile.ZIP_STORED
                        or ((entry.external_attr >> 16) & 0o170000) == 0o120000):
                    raise BundleError("Archive has unsafe, duplicate or unsupported entries.")
                found.add(entry.filename)
                total += entry.file_size
                if total > MAX_BUNDLE or entry.file_size > 64 * 1024:
                    raise BundleError("Archive contains oversized profiles.")
                raw = archive.read(entry)
                try:
                    parse_supported_profile(entry.filename[:-5], raw.decode("utf-8"))
                except (UnicodeError, ProfileValidationError):
                    raise BundleError(
                        "Backup contains configuration syntax not supported for safe batch import. "
                        "No profiles have been changed."
                    ) from None
            return tuple(sorted(found, key=str.casefold))
    except (zipfile.BadZipFile, RuntimeError, EOFError, ValueError) as exc:
        if isinstance(exc, BundleError):
            raise
        raise BundleError("Invalid WireGuard ZIP backup.") from None


def save_bundle(data: bytes, destination: Path, *, allowed_root: Path | None = None) -> Path:
    if not data or len(data) > MAX_BUNDLE or not zipfile.is_zipfile(io.BytesIO(data)):
        raise BundleError("Invalid or oversized native-profile archive.")
    if os.geteuid() == 0:
        raise BundleError("Archive export must run as the desktop user, not as root.")
    destination = Path(destination)
    if destination.suffix.lower() != ".zip":
        raise BundleError("Choose a .zip filename.")
    root = (allowed_root or Path.home()).resolve()
    try:
        parent = destination.parent.resolve(strict=True)
    except OSError:
        raise BundleError("Export directory is not accessible.") from None
    if not parent.is_dir() or not parent.is_relative_to(root):
        raise BundleError("Export must be saved inside your home directory.")
    target = parent / destination.name
    fd = None
    created = False
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = True
        with os.fdopen(fd, "wb") as out:
            fd = None
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise BundleError("Backup already exists; no overwrite was performed.") from None
    except OSError:
        if fd is not None:
            os.close(fd)
        # Never delete or overwrite a pre-existing user file on export failure.
        if created:
            target.unlink(missing_ok=True)
        raise BundleError("Unable to save ZIP backup safely.") from None
    return target
