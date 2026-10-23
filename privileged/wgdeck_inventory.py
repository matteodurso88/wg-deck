#!/usr/bin/python3
"""Publish native WireGuard names and sanitized RX/TX metrics.

Root-owned oneshot invoked by both a directory watcher and a 10-second timer.
Never opens profile contents, logs peer public keys, or executes wg-quick.
The Debian package publishes root-owned, non-secret names and aggregate traffic
metadata for all local users by default (0644), so newly installed desktops
work immediately. An administrator may opt into primary-group-only reads (0640).
No configuration contents, endpoints or private keys are published.
"""
from __future__ import annotations

import os
import re
import stat
import tempfile
import subprocess
import time
from pathlib import Path

SYSTEM_DIR = Path("/etc/wireguard")
SNAPSHOT = Path("/run/wg-deck-profiles.list")
TRAFFIC_SNAPSHOT = Path("/run/wg-deck-traffic.tsv")
MAX_TRAFFIC_BYTES = 16 * 1024
WG = "/usr/bin/wg"
READER_GID = Path("/etc/wg-deck-reader-gid")
NAME = re.compile(r"[A-Za-z0-9_=+.-]{1,15}\Z")


def native_profiles(directory: Path) -> tuple[str, ...]:
    names = set()
    with os.scandir(directory) as iterator:
        for entry in iterator:
            if not entry.name.endswith(".conf"):
                continue
            name = entry.name[:-5]
            if name in (".", "..") or not NAME.fullmatch(name):
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            names.add(name)
    return tuple(sorted(names, key=str.casefold))


def configured_group(path: Path = READER_GID) -> int:
    # Missing config is the standard Debian install: root group and world-
    # readable non-secret metadata. Other errors must fail closed.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return 0
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("Invalid root-owned reader group configuration.")
        raw = os.read(fd, 32)
    finally:
        os.close(fd)
    value = raw.strip()
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError("Invalid reader group.")
    gid = int(value)
    if gid < 0 or gid > 2**31 - 1:
        raise ValueError("Reader group out of range.")
    return gid


def publish(directory: Path = SYSTEM_DIR, destination: Path = SNAPSHOT,
            *, reader_gid: int | None = None) -> tuple[str, ...]:
    if os.geteuid() != 0:
        raise PermissionError("Root-owned inventory publisher required.")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("WireGuard configuration directory is not safe.")
    if reader_gid is None:
        reader_gid = configured_group()
    names = native_profiles(directory)
    data = (("\n".join(names) + "\n") if names else "").encode("ascii")
    fd, staged = tempfile.mkstemp(prefix=".wgdeck-profiles-", dir=destination.parent)
    try:
        os.fchown(fd, 0, reader_gid)
        os.fchmod(fd, 0o644 if reader_gid == 0 else 0o640)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, destination)
        dir_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return names


def _wg_lines(*args: str) -> str | None:
    """Allowlisted read-only wg requests. Never log stdout (peer public keys)."""
    if args not in (("show", "interfaces"),) and not (
        len(args) == 3 and args[0] == "show"
        and NAME.fullmatch(args[1]) and args[1] not in {".", ".."}
        and args[2] in {"transfer", "latest-handshakes"}
    ):
        return None
    try:
        result = subprocess.run(
            (WG, *args), capture_output=True, text=True,
            env={"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
            timeout=4, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or len(result.stdout) > 128_000:
        return None
    return result.stdout


def _aggregate_transfer(raw: str | None) -> tuple[int, int] | None:
    if raw is None:
        return None
    rx = tx = 0
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 3:
            return None
        try:
            received, sent = int(parts[1]), int(parts[2])
        except ValueError:
            return None
        if min(received, sent) < 0:
            return None
        rx += received
        tx += sent
    return rx, tx


def _latest_handshake(raw: str | None) -> int | None:
    if raw is None:
        return None
    stamps = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            return None
        try:
            stamp = int(parts[1])
        except ValueError:
            return None
        if stamp < 0:
            return None
        if stamp:
            stamps.append(stamp)
    return max(stamps) if stamps else 0


def publish_traffic(
    names: tuple[str, ...],
    destination: Path = TRAFFIC_SNAPSHOT,
    *, reader_gid: int | None = None, now: int | None = None,
) -> None:
    """Publish a sanitized, privileged 10-second transfer snapshot.

    Format WGDECK-TRAFFIC-V1 <epoch>\n followed by only
    native-interface-name, UP/DOWN, RX, TX, latest-handshake.
    No public keys, endpoints, commands, config bytes or stderr are persisted.
    Fail closed on any unavailable counter; represent it as '-' not zero.
    """
    if os.geteuid() != 0:
        raise PermissionError("Root-only metrics publisher required.")
    if reader_gid is None:
        reader_gid = configured_group()
    timestamp = int(time.time()) if now is None else now
    interfaces = _wg_lines("show", "interfaces")
    if interfaces is None:
        # A missing kernel/permission result must not be published as all DOWN.
        # The UI rejects the stale previous snapshot after 30s.
        return
    active = {
        name for name in interfaces.split()
        if NAME.fullmatch(name) and name not in {".", ".."}
    }
    lines = [f"WGDECK-TRAFFIC-V1\t{timestamp}"]
    for name in sorted(set(names), key=str.casefold):
        if not NAME.fullmatch(name) or name in {".", ".."}:
            continue
        if name not in active:
            lines.append(f"{name}\tDOWN\t0\t0\t0")
            continue
        totals = _aggregate_transfer(_wg_lines("show", name, "transfer"))
        stamp = _latest_handshake(_wg_lines("show", name, "latest-handshakes"))
        rx, tx = totals if totals is not None else ("-", "-")
        latest = stamp if stamp is not None else "-"
        lines.append(f"{name}\tUP\t{rx}\t{tx}\t{latest}")
    payload = ("\n".join(lines) + "\n").encode("ascii")
    if len(payload) > MAX_TRAFFIC_BYTES:
        raise ValueError("Traffic snapshot over safety bound.")
    fd, staged = tempfile.mkstemp(prefix=".wgdeck-traffic-", dir=destination.parent)
    try:
        os.fchown(fd, 0, reader_gid)
        os.fchmod(fd, 0o644 if reader_gid == 0 else 0o640)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, destination)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


if __name__ == "__main__":
    published = publish()
    # Names must still be published even when the kernel/tools cannot expose
    # counters. No failure here should trigger a privileged GUI prompt.
    publish_traffic(published)
