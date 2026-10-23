"""Read a root-owned, secret-free WireGuard transfer snapshot.

The root systemd publisher is the sole privileged reader. The UI sees only
interface names, up/down flags, aggregate RX/TX bytes and handshake timestamps;
it never needs CAP_NET_ADMIN or repeated Polkit grants to monitor traffic.
"""
from __future__ import annotations

import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from .discovery import valid_interface

TRAFFIC_SNAPSHOT = Path("/run/wg-deck-traffic.tsv")
MAX_BYTES = 16 * 1024
MAX_AGE_SECONDS = 30
MAX_COUNTER = (1 << 64) - 1
_HEADER = re.compile(r"WGDECK-TRAFFIC-V1\t([0-9]{1,12})\Z")


@dataclass(frozen=True, slots=True)
class TrafficRow:
    is_up: bool
    rx_bytes: int | None
    tx_bytes: int | None
    latest_handshake: int | None


def _counter(value: str) -> int | None:
    if value == "-":
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 20:
        raise ValueError("Invalid counter.")
    number = int(value)
    if number > MAX_COUNTER:
        raise ValueError("Counter exceeded the 64-bit range.")
    return number


def parse_traffic_snapshot(raw: bytes, *, now: int | None = None) -> dict[str, TrafficRow]:
    text = raw.decode("ascii")
    lines = text.splitlines()
    if not lines:
        raise ValueError("Missing header.")
    match = _HEADER.fullmatch(lines[0])
    if not match:
        raise ValueError("Invalid traffic version.")
    timestamp = int(match.group(1))
    current = int(time.time()) if now is None else now
    if timestamp > current + 2 or current - timestamp > MAX_AGE_SECONDS:
        raise ValueError("Traffic data is stale or future-dated.")
    if len(lines) > 101:
        raise ValueError("Too many traffic records.")
    found: dict[str, TrafficRow] = {}
    for record in lines[1:]:
        parts = record.split("\t")
        if len(parts) != 5:
            raise ValueError("Malformed traffic record.")
        name, status, rx_raw, tx_raw, stamp_raw = parts
        if not valid_interface(name) or name in found or status not in {"UP", "DOWN"}:
            raise ValueError("Invalid interface record.")
        rx, tx, stamp = (_counter(value) for value in (rx_raw, tx_raw, stamp_raw))
        if status == "DOWN" and (rx, tx, stamp) != (0, 0, 0):
            raise ValueError("Inactive interface has inconsistent metrics.")
        found[name] = TrafficRow(
            status == "UP", rx, tx,
            stamp if stamp not in (None, 0) else None,
        )
    return found


def read_native_traffic(
    path: Path = TRAFFIC_SNAPSHOT, *, now: int | None = None,
) -> dict[str, TrafficRow] | None:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            return None
        if info.st_size > MAX_BYTES:
            return None
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        return parse_traffic_snapshot(data, now=now)
    except (OSError, UnicodeError, ValueError):
        return None
    finally:
        os.close(fd)
