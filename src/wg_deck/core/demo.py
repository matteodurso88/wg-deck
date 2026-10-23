"""Clearly labeled synthetic data used only with --demo."""

from __future__ import annotations

from .discovery import Inventory
from .models import ProfileSnapshot, TunnelState


def demo_inventory() -> Inventory:
    return Inventory(
        profiles=(
            ProfileSnapshot("office-vpn", TunnelState.UP, "vpn.example.com:51820", None, 83_300_000, 42_100_000),
            ProfileSnapshot("home-lab", TunnelState.DOWN),
            ProfileSnapshot("demo-edge", TunnelState.UP, "203.0.113.42:51820", None, 12_800_000, 4_100_000),
            ProfileSnapshot("test-net", TunnelState.DOWN),
            ProfileSnapshot("mobile", TunnelState.UP, "192.0.2.20:51820", None, 8_400_000, 2_700_000),
        ),
        warnings=("DEMO DATA: sample profiles are fictional, and no commands are executed.",),
        wg_version="Demo",
        wireguard_tools=False,
    )
