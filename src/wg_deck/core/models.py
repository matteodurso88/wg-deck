"""Domain states; no runtime networking side effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TunnelState(str, Enum):
    UNKNOWN = "unknown"
    DOWN = "down"
    UP = "up"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    name: str
    state: TunnelState = TunnelState.UNKNOWN
    endpoint: str | None = None
    last_handshake: int | None = None
    # None = counter not observable; never present it as a real zero.
    rx_bytes: int | None = 0
    tx_bytes: int | None = 0
