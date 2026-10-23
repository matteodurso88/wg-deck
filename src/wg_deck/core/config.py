"""Bounded, read-only WireGuard .conf inspection.

Preserves secrets only in the caller's process memory to populate password fields;
never logs, rewrites, executes hooks, or persists an imported configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigSummary:
    address: str | None = None
    listen_port: int | None = None
    private_key: str | None = None
    dns: str | None = None
    mtu: int | None = None
    first_peer_key: str | None = None
    first_peer_preshared_key: str | None = None
    first_peer_endpoint: str | None = None
    first_peer_allowed_ips: str | None = None
    first_peer_keepalive: int | None = None
    peer_count: int = 0
    hooks: tuple[str, ...] = ()


def _int_or_none(value: str) -> int | None:
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= 65535 else None


def inspect_config(text: str) -> ConfigSummary:
    if len(text) > 128 * 1024 or "\x00" in text:
        raise ValueError("Malformed or oversized configuration.")
    section = ""
    interface: dict[str, str] = {}
    peer: dict[str, str] = {}
    peer_count = 0
    hooks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().casefold()
            if section == "peer":
                peer_count += 1
            continue
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        low = key.casefold()
        if section == "interface":
            if low in {"preup", "postup", "predown", "postdown"}:
                hooks.append(key)
            interface[low] = value
        elif section == "peer" and peer_count == 1:
            peer[low] = value
    return ConfigSummary(
        address=interface.get("address"),
        listen_port=_int_or_none(interface["listenport"]) if "listenport" in interface else None,
        private_key=interface.get("privatekey"),
        dns=interface.get("dns"),
        mtu=_int_or_none(interface["mtu"]) if "mtu" in interface else None,
        first_peer_key=peer.get("publickey"),
        first_peer_preshared_key=peer.get("presharedkey"),
        first_peer_endpoint=peer.get("endpoint"),
        first_peer_allowed_ips=peer.get("allowedips"),
        first_peer_keepalive=_int_or_none(peer["persistentkeepalive"]) if "persistentkeepalive" in peer else None,
        peer_count=peer_count,
        hooks=tuple(hooks),
    )
