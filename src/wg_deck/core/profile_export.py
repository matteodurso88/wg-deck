"""Create new WireGuard .conf profiles without privileged system writes.

Only owner-requested exports inside an approved user directory are possible.
No imported configuration is serialized here: unknown directives and hooks must
never be silently lost or accidentally executed.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .discovery import valid_interface


class ProfileValidationError(ValueError):
    """Public, non-secret validation error."""


@dataclass(frozen=True, slots=True, repr=False)
class PeerDraft:
    public_key: str
    allowed_ips: str
    endpoint: str = ""
    preshared_key: str = ""
    keepalive: int = 0


@dataclass(frozen=True, slots=True, repr=False)
class ProfileDraft:
    name: str
    address: str
    private_key: str
    peers: tuple[PeerDraft, ...]
    dns: str = ""
    listen_port: int = 0
    mtu: int = 0


def _key(value: str, label: str) -> str:
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ProfileValidationError(f"{label} must be a base64-encoded WireGuard key.") from None
    if len(raw) != 32 or base64.b64encode(raw).decode("ascii") != value:
        raise ProfileValidationError(f"{label} must encode exactly 32 bytes.")
    return value


def _addresses(value: str, *, networks: bool) -> str:
    label = "Allowed IPs" if networks else "Interface Address"
    if not value.strip():
        raise ProfileValidationError(
            f"{label} is required. Example: "
            + ("198.18.77.1/32" if networks else "198.18.77.2/32")
            + ". Placeholder examples are not inserted automatically."
        )
    components = [component.strip() for component in value.split(",")]
    if any(not component for component in components):
        raise ProfileValidationError(f"{label}: remove empty entries and trailing commas.")
    try:
        for component in components:
            if networks:
                ipaddress.ip_network(component, strict=False)
            else:
                ipaddress.ip_interface(component)
    except ValueError:
        raise ProfileValidationError(f"{label}: enter valid IP addresses with CIDR prefixes.") from None
    return ", ".join(components)


def _dns(value: str) -> str:
    if not value:
        return ""
    entries = [item.strip() for item in value.split(",")]
    try:
        for entry in entries:
            ipaddress.ip_address(entry)
    except ValueError:
        raise ProfileValidationError("DNS accepts IP addresses only in this release.") from None
    return ", ".join(entries)


def _endpoint(value: str) -> str:
    if not value:
        return ""
    if any(char.isspace() for char in value) or any(char in value for char in "#;%\\\n\r"):
        raise ProfileValidationError("Invalid peer endpoint.")
    if value.startswith("["):
        match = re.fullmatch(r"\[([0-9A-Fa-f:.%]+)\]:(\d{1,5})", value)
        if not match:
            raise ProfileValidationError("Expected an IPv6 endpoint in [host]:port format.")
        try:
            ipaddress.IPv6Address(match[1])
        except ValueError:
            raise ProfileValidationError("Invalid IPv6 peer endpoint.") from None
        port = int(match[2])
    else:
        match = re.fullmatch(r"([A-Za-z0-9.-]+):(\d{1,5})", value)
        if not match or len(match[1]) > 253 or any(
            not part or len(part) > 63 or part.startswith("-") or part.endswith("-")
            for part in match[1].split(".")
        ):
            raise ProfileValidationError("Invalid hostname or IPv4 endpoint.")
        port = int(match[2])
    if not 1 <= port <= 65535:
        raise ProfileValidationError("Peer endpoint port must be 1–65535.")
    return value


def render_new_profile(profile: ProfileDraft) -> str:
    """Validate and serialize known wg-quick fields only, without hooks."""
    if not valid_interface(profile.name):
        raise ProfileValidationError("Invalid interface name (1–15 safe characters).")
    address = _addresses(profile.address, networks=False)
    private_key = _key(profile.private_key, "PrivateKey")
    if not profile.peers:
        raise ProfileValidationError("At least one peer is required.")
    if not isinstance(profile.listen_port, int) or not 0 <= profile.listen_port <= 65535:
        raise ProfileValidationError("ListenPort must be 0–65535.")
    if not isinstance(profile.mtu, int) or (profile.mtu and not 576 <= profile.mtu <= 9000):
        raise ProfileValidationError("MTU must be 576–9000 or automatic.")
    lines = ["[Interface]", f"PrivateKey = {private_key}", f"Address = {address}"]
    if profile.listen_port:
        lines.append(f"ListenPort = {profile.listen_port}")
    if profile.dns:
        lines.append(f"DNS = {_dns(profile.dns)}")
    if profile.mtu:
        lines.append(f"MTU = {profile.mtu}")
    for peer in profile.peers:
        public_key = _key(peer.public_key, "PublicKey")
        allowed_ips = _addresses(peer.allowed_ips, networks=True)
        if not isinstance(peer.keepalive, int) or not 0 <= peer.keepalive <= 65535:
            raise ProfileValidationError("PersistentKeepalive must be 0–65535.")
        endpoint = _endpoint(peer.endpoint)
        lines.extend(["", "[Peer]", f"PublicKey = {public_key}", f"AllowedIPs = {allowed_ips}"])
        if peer.preshared_key:
            lines.append(f"PresharedKey = {_key(peer.preshared_key, 'PresharedKey')}")
        if endpoint:
            lines.append(f"Endpoint = {endpoint}")
        if peer.keepalive:
            lines.append(f"PersistentKeepalive = {peer.keepalive}")
    return "\n".join(lines) + "\n"


def export_new_profile(
    profile: ProfileDraft, destination: Path, *, allowed_root: Path | None = None
) -> Path:
    """Create exclusively (0600) under HOME or a test-specific allowed directory.

    No overwrites or symlink following. The application must run unprivileged.
    """
    data = render_new_profile(profile).encode("utf-8")
    if os.geteuid() == 0:
        raise ProfileValidationError("Export must be run as an unprivileged user.")
    destination = Path(destination)
    if destination.suffix != ".conf" or destination.stem != profile.name:
        raise ProfileValidationError("Filename must match the interface name and end in .conf.")
    root = (allowed_root or Path.home()).resolve()
    try:
        parent = destination.parent.resolve(strict=True)
    except OSError:
        raise ProfileValidationError("Export directory is unavailable.") from None
    if not parent.is_relative_to(root) or not parent.is_dir():
        raise ProfileValidationError("Export directory must be inside the allowed user directory.")
    target = parent / destination.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    created = False
    try:
        fd = os.open(target, flags, 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise ProfileValidationError("An export with this filename already exists.") from None
    except OSError:
        if fd is not None:
            os.close(fd)
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        raise ProfileValidationError("Unable to save the new profile safely.") from None
    return target


def parse_supported_profile(name: str, text: str) -> ProfileDraft:
    """Losslessly accept the narrow editable v1 subset; reject all other options.

    Unlike the preview-only inspector, this parser refuses executable hooks,
    duplicate options, unknown directives and malformed sections. It never
    silently drops a peer or directive. The installed helper validates again.
    """
    if len(text.encode("utf-8")) > 64 * 1024 or "\x00" in text:
        raise ProfileValidationError("Profile oversized or invalid.")
    if not valid_interface(name):
        raise ProfileValidationError("Invalid profile name.")
    section = ""
    interface: dict[str, str] = {}
    peers: list[dict[str, str]] = []
    allowed_interface = {"privatekey", "address", "listenport", "dns", "mtu"}
    allowed_peer = {
        "publickey", "presharedkey", "endpoint", "allowedips", "persistentkeepalive"
    }
    for raw in text.splitlines():
        value = raw.strip()
        if not value or value.startswith(("#", ";")):
            continue
        if value in ("[Interface]", "[Peer]"):
            if value == "[Interface]":
                if section or peers:
                    raise ProfileValidationError("Only one Interface section is permitted.")
                section = "interface"
            else:
                if section not in {"interface", "peer"}:
                    raise ProfileValidationError("A Peer requires an Interface.")
                section = "peer"
                peers.append({})
            continue
        if "=" not in value or not section:
            raise ProfileValidationError("Unsupported profile syntax.")
        key, field = (s.strip() for s in value.split("=", 1))
        lower = key.casefold()
        dest = interface if section == "interface" else peers[-1]
        allowed = allowed_interface if section == "interface" else allowed_peer
        if lower not in allowed or lower in dest or not field:
            raise ProfileValidationError("Unknown, duplicate or empty directive; import remains preview-only.")
        if any(char in field for char in ("\r", "\n", "\\", "#", ";")):
            raise ProfileValidationError("Unsupported field characters.")
        dest[lower] = field
    if not peers or not {"address", "privatekey"} <= interface.keys():
        raise ProfileValidationError("Interface key/address and at least one Peer are required.")
    try:
        profile = ProfileDraft(
            name=name,
            address=interface["address"],
            private_key=interface["privatekey"],
            peers=tuple(
                PeerDraft(
                    public_key=p["publickey"],
                    allowed_ips=p["allowedips"],
                    endpoint=p.get("endpoint", ""),
                    preshared_key=p.get("presharedkey", ""),
                    keepalive=int(p.get("persistentkeepalive", "0")),
                ) for p in peers
            ),
            dns=interface.get("dns", ""),
            listen_port=int(interface.get("listenport", "0")),
            mtu=int(interface.get("mtu", "0")),
        )
    except (KeyError, TypeError, ValueError):
        raise ProfileValidationError("Invalid or missing mandatory profile field.") from None
    render_new_profile(profile)
    return profile
