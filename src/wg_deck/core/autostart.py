"""Opt-in, unprivileged XDG session autostart for the desktop GUI.

This creates/removes only a managed per-user desktop entry. It does not
start tunnels, grant privileges, alter DNS, or modify system services.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

DESKTOP_FILE = "org.matt88.wg-deck.desktop"


class AutostartError(RuntimeError):
    """Safe message suitable for the Settings UI."""


def _destination(config_home: Path | None) -> Path:
    raw = config_home if config_home is not None else os.environ.get("XDG_CONFIG_HOME")
    base = Path(raw).expanduser() if raw else Path.home() / ".config"
    if not base.is_absolute():
        raise AutostartError("XDG_CONFIG_HOME must be an absolute directory.")
    return base / "autostart" / DESKTOP_FILE


def _entry(launcher: Path | None) -> bytes:
    script = launcher if launcher is not None else (
        Path(__file__).resolve().parents[3] / "scripts" / "run.sh"
    )
    script = Path(script)
    # The Desktop Entry Exec syntax is not a shell. Limit to portable
    # paths (spaces are quoted); reject field codes, escape sequences and
    # control characters rather than forming an ambiguous login command.
    if not script.is_absolute() or not re.fullmatch(r"[A-Za-z0-9 /._+@~:-]+", str(script)):
        raise AutostartError("Unsupported application path for desktop autostart.")
    if not script.is_file():
        raise AutostartError("Application launcher is missing; restore scripts/run.sh.")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=WG Deck\n"
        "Comment=Start WG Deck at desktop login (no VPN auto-connect)\n"
        f'Exec=/usr/bin/bash "{script}"\n'
        "TryExec=/usr/bin/bash\n"
        "Terminal=false\n"
        "StartupNotify=true\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-WG-Deck-Managed=true\n"
    ).encode("utf-8")


def _is_owned(data: bytes, launcher: Path | None) -> bool:
    return data == _entry(launcher)


def is_enabled(*, config_home: Path | None = None,
               launcher: Path | None = None) -> bool:
    """Read the actual XDG entry, never a possibly stale QSettings flag."""
    try:
        target = _destination(config_home)
        return (not target.is_symlink() and target.is_file()
                and _is_owned(target.read_bytes(), launcher))
    except (OSError, AutostartError):
        return False


def set_enabled(enabled: bool, *, config_home: Path | None = None,
                launcher: Path | None = None) -> None:
    """Enable or disable only the entry belonging to this app.

    Existing, different or symlinked entries are never overwritten/deleted.
    """
    if os.geteuid() == 0:
        raise AutostartError("Autostart must be configured by the desktop user.")
    target = _destination(config_home)
    expected = _entry(launcher)
    parent = target.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise AutostartError("The autostart directory is not a regular directory.")
    if enabled:
        try:
            parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except FileExistsError:
            if is_enabled(config_home=config_home, launcher=launcher):
                return
            raise AutostartError(
                "An existing login entry differs from WG Deck; it was not changed."
            ) from None
        except OSError:
            raise AutostartError("Unable to create the user autostart entry.") from None
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(expected)
                output.flush()
                os.fsync(output.fileno())
        except OSError:
            target.unlink(missing_ok=True)
            raise AutostartError("Unable to save the user autostart entry.") from None
    else:
        if target.is_symlink():
            raise AutostartError("Autostart entry is a symlink; refusing to remove it.")
        try:
            actual = target.read_bytes()
        except FileNotFoundError:
            return
        except OSError:
            raise AutostartError("Unable to read the user autostart entry.") from None
        if not _is_owned(actual, launcher):
            raise AutostartError(
                "An existing login entry differs from WG Deck; it was not removed."
            )
        try:
            target.unlink()
        except OSError:
            raise AutostartError("Unable to disable the user autostart entry.") from None
