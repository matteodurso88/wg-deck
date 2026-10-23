"""Unprivileged, strictly read-only WireGuard inventory.

Never parses file contents under /etc/wireguard, calls wg showconf, or logs keys.
Connection state is based on observed interfaces, not config file existence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import ProfileSnapshot, TunnelState

INTERFACE_RE = re.compile(r"^[A-Za-z0-9_=+.-]{1,15}$")
SERVICE_RE = re.compile(r"^wg-quick@([A-Za-z0-9_=+.-]{1,15})\.service$")
CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]


@dataclass(frozen=True, slots=True)
class Inventory:
    profiles: tuple[ProfileSnapshot, ...]
    warnings: tuple[str, ...]
    wg_version: str = "Unavailable"
    wireguard_tools: bool = False


def valid_interface(name: str) -> bool:
    return bool(INTERFACE_RE.fullmatch(name)) and name not in {".", ".."}


def parse_interface_names(output: str) -> set[str]:
    return {name for name in output.split() if valid_interface(name)}


def parse_systemd_instances(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        first = line.strip().split(maxsplit=1)
        if first:
            match = SERVICE_RE.fullmatch(first[0])
            if match:
                names.add(match.group(1))
    return names


def parse_transfer(output: str) -> tuple[int, int]:
    rx = tx = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            received, sent = int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if received >= 0 and sent >= 0:
            rx += received
            tx += sent
    return rx, tx


def parse_handshake(output: str) -> int | None:
    values: list[int] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            stamp = int(parts[1])
        except ValueError:
            continue
        if stamp > 0:
            values.append(stamp)
    return max(values) if values else None


def parse_endpoint(output: str) -> str | None:
    for line in output.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[1] != "(none)":
            return parts[1][:256]
    return None


def parse_ip_links(output: str) -> set[str]:
    try:
        links = json.loads(output)
    except (ValueError, TypeError):
        return set()
    if not isinstance(links, list):
        return set()
    return {
        entry["ifname"]
        for entry in links
        if isinstance(entry, dict)
        and isinstance(entry.get("ifname"), str)
        and valid_interface(entry["ifname"])
    }


def scan_config_names(directories: tuple[Path, ...]) -> tuple[set[str], bool]:
    """Names only, never open/read a config or follow symlinks."""
    found: set[str] = set()
    inaccessible = False
    for directory in directories:
        try:
            with os.scandir(directory) as items:
                for item in items:
                    if not item.name.endswith(".conf"):
                        continue
                    name = item.name[:-5]
                    if valid_interface(name) and item.is_file(follow_symlinks=False):
                        found.add(name)
        except FileNotFoundError:
            pass
        except (PermissionError, OSError):
            inaccessible = True
    return found, inaccessible


def system_runner(args: tuple[str, ...]) -> tuple[int, str]:
    """Run only fixed read-only commands; never shell, never arbitrary user args."""
    fixed = {
        ("wg", "--version"),
        ("wg", "show", "interfaces"),
        ("ip", "-j", "link", "show", "type", "wireguard"),
        ("systemctl", "list-unit-files", "--type=service", "--no-legend", "--no-pager", "wg-quick@*.service"),
    }
    if args not in fixed:
        if not (
            len(args) == 4
            and args[0:2] == ("wg", "show")
            and valid_interface(args[2])
            and args[3] in {"endpoints", "latest-handshakes", "transfer"}
        ):
            return 127, ""
    executable = shutil.which(args[0])
    if executable is None:
        return 127, ""
    try:
        result = subprocess.run(
            (executable, *args[1:]),
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
            env={"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return 126, ""
    return result.returncode, result.stdout[:128_000]


def discover(
    *,
    directories: tuple[Path, ...] | None = None,
    runner: CommandRunner = system_runner,
    extra_names: tuple[str, ...] = (),
) -> Inventory:
    """Discover profile names and safe connection metrics.

    Unreadable directories or unprivileged 'wg' calls are expected on Linux.
    They remain explicit limitations, never fabricated success.
    """
    if directories is None:
        directory = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        directories = (Path("/etc/wireguard"), directory / "wireguard")

    names, inaccessible = scan_config_names(directories)
    # Names registered locally after privileged install: the /etc/wireguard
    # directory is usually 0700 and its filenames are not visible to users.
    names.update(name for name in extra_names if valid_interface(name))
    warnings: list[str] = []
    if inaccessible:
        warnings.append("Some configuration directories are inaccessible to this user.")

    wg_status, wg_stdout = runner(("wg", "show", "interfaces"))
    if wg_status == 0:
        active = parse_interface_names(wg_stdout)
    else:
        active = set()
        warnings.append("wg interface inventory is unavailable without additional permissions.")

    ip_status, ip_stdout = runner(("ip", "-j", "link", "show", "type", "wireguard"))
    if ip_status == 0:
        active.update(parse_ip_links(ip_stdout))

    unit_status, units = runner(("systemctl", "list-unit-files", "--type=service", "--no-legend", "--no-pager", "wg-quick@*.service"))
    if unit_status == 0:
        names.update(parse_systemd_instances(units))
    names.update(active)

    version_status, version_text = runner(("wg", "--version"))
    wg_version = version_text.splitlines()[0][:120] if version_status == 0 and version_text.strip() else "Unavailable"

    status_observable = wg_status == 0 or ip_status == 0
    profiles: list[ProfileSnapshot] = []
    for name in sorted(names, key=str.casefold):
        state = (
            TunnelState.UP if name in active else
            TunnelState.DOWN if status_observable else TunnelState.UNKNOWN
        )
        endpoint = None
        handshake = None
        # A transfer counter is zero only if it was *actually* observed.
        rx = tx = None if name in active else 0
        if name in active and wg_status == 0:
            # Fixed commands, interface name validated above.
            ep_code, ep = runner(("wg", "show", name, "endpoints"))
            hs_code, hs = runner(("wg", "show", name, "latest-handshakes"))
            tx_code, transfer = runner(("wg", "show", name, "transfer"))
            if ep_code == 0:
                endpoint = parse_endpoint(ep)
            if hs_code == 0:
                handshake = parse_handshake(hs)
            if tx_code == 0:
                rx, tx = parse_transfer(transfer)
        profiles.append(ProfileSnapshot(name, state, endpoint, handshake, rx, tx))

    if not names:
        warnings.append("No visible profiles: check config directory permissions and installed tools.")
    return Inventory(tuple(profiles), tuple(warnings), wg_version, version_status == 0)
