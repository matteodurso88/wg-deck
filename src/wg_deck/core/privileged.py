"""Polkit bridge shared by ALL WireGuard profiles, regardless of origin.

No shell, arbitrary paths, saved passwords, stored private keys or secret logs.
Reading a system configuration is an explicitly authorized operation.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .discovery import valid_interface

MAX_BUNDLE = 2 * 1024 * 1024
HELPER = Path("/usr/local/libexec/wg-deck-helper")
CONNECTION_HELPER = Path("/usr/local/libexec/wg-deck-connection")
CONNECTION_POLICY = Path("/usr/share/polkit-1/actions/org.matt88.wgdeck.connection.policy")
READ_HELPER = Path("/usr/local/libexec/wg-deck-read")
READ_POLICY = Path("/usr/share/polkit-1/actions/org.matt88.wgdeck.read.policy")
_ALLOWED = frozenset(("install", "up", "down", "replace", "read", "list", "delete", "bundle", "install-bundle"))


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str


@dataclass(frozen=True, repr=False)
class ConfigResult:
    ok: bool
    message: str
    name: str = ""
    content: str = ""
    revision: str = ""


@dataclass(frozen=True)
class InventoryResult:
    ok: bool
    message: str
    names: tuple[str, ...] = ()


@dataclass(frozen=True, repr=False)
class BundleResult:
    ok: bool
    message: str
    data: bytes = b""


def available() -> bool:
    if shutil.which("pkexec") is None:
        return False
    try:
        info = HELPER.stat()
        trusted = (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                   and not info.st_mode & 0o022 and bool(info.st_mode & 0o111))
        if not trusted:
            return False
        # During Local-First development require the root-installed helper to
        # match the current checked-out version; otherwise stale managed-only
        # code would still be callable after a git pull.
        source = Path(__file__).resolve().parents[3] / "privileged" / "wgdeck_helper.py"
        if source.is_file():
            return hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(
                HELPER.read_bytes()
            ).digest()
        return True
    except OSError:
        return False


def connection_available() -> bool:
    """Independent root-owned dispatcher + source integrity for toggle actions."""
    if not available():
        return False
    try:
        info = CONNECTION_HELPER.stat()
        if not (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and not info.st_mode & 0o022 and info.st_mode & 0o111):
            return False
        policy_info = CONNECTION_POLICY.stat()
        if not (stat.S_ISREG(policy_info.st_mode) and policy_info.st_uid == 0
                and not policy_info.st_mode & 0o022):
            return False
        source_dir = Path(__file__).resolve().parents[3] / "privileged"
        for installed, source in (
            (CONNECTION_HELPER, source_dir / "wgdeck_connection.py"),
            (CONNECTION_POLICY, source_dir / "org.matt88.wgdeck.connection.policy"),
        ):
            if source.is_file() and hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(
                installed.read_bytes()
            ).digest():
                return False
        return True
    except OSError:
        return False


def read_available() -> bool:
    """Whether the short-term Polkit token for secret-bearing reads is installed."""
    if not available():
        return False
    try:
        executable = READ_HELPER.stat()
        policy = READ_POLICY.stat()
        if not (stat.S_ISREG(executable.st_mode) and executable.st_uid == 0
                and not executable.st_mode & 0o022 and executable.st_mode & 0o111):
            return False
        if not (stat.S_ISREG(policy.st_mode) and policy.st_uid == 0
                and not policy.st_mode & 0o022):
            return False
        source_dir = Path(__file__).resolve().parents[3] / "privileged"
        for installed, source in (
            (READ_HELPER, source_dir / "wgdeck_read.py"),
            (READ_POLICY, source_dir / "org.matt88.wgdeck.read.policy"),
        ):
            if source.is_file() and hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(
                installed.read_bytes()
            ).digest():
                return False
        return True
    except OSError:
        return False


def _invoke(action: str, name: str, payload: bytes = b"") -> tuple[bool, bytes]:
    if action not in _ALLOWED or (
        (action in {"list", "bundle", "install-bundle"} and name != "all") or
        (action not in {"list", "bundle", "install-bundle"} and not valid_interface(name))
    ):
        return False, b""
    limit = MAX_BUNDLE if action == "install-bundle" else 64 * 1024 + 128
    if not available() or len(payload) > limit:
        return False, b""
    # Only connection operations use the brief Polkit auth cache.
    # Keep file read/write operations on their strictly per-call auth policy.
    if action in {"up", "down"} and not connection_available():
        return False, b""
    # Secret reads and exports have their own limited reusable Polkit grant.
    # Fall back to the stricter helper until the read-only policy is installed.
    if action in {"up", "down"}:
        executable = CONNECTION_HELPER
    elif action in {"read", "bundle"} and read_available():
        executable = READ_HELPER
    else:
        executable = HELPER
    if action not in {"install", "replace", "install-bundle"} and payload:
        return False, b""
    try:
        result = subprocess.run(
            ("pkexec", str(executable), action, name),
            input=payload,
            capture_output=True,
            check=False,
            timeout=75,
            env={
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "LC_ALL": "C",
                "DISPLAY": os.environ.get("DISPLAY", ""),
                "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", ""),
                "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
            },
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, b""
    if result.returncode == 0 and result.stdout.startswith(b"OK:"):
        max_response = MAX_BUNDLE + 64 if action == "bundle" else 64 * 1024 + 128
        if len(result.stdout) > max_response:
            return False, b""
        return True, result.stdout
    # Do not expose stderr from wg-quick or third-party hooks; only exact
    # fixed, secret-free helper diagnostic phrases are safe for the GUI.
    allowed_reasons = {
        b"Unsafe config owner or writable permissions.",
        b"Unsafe directory ownership/permissions.",
        b"Unsafe directory link.",
        b"Configuration oversized.",
        b"Disconnect the active tunnel before deleting the profile.",
        b"Disable the wg-quick systemd unit before deleting its profile.",
        b"Profile changed or reactivated; deletion cancelled.",
        b"An existing backup does not match; deletion cancelled.",
        b"Profile already exists. No overwrites are allowed.",
        b"Privileged operation unavailable.",
        b"No profiles or too many profiles for a backup.",
        b"Profile archive exceeds the size limit.",
        b"Invalid or oversized profile archive.",
        b"Invalid profile archive entry count.",
        b"Archive must contain only native .conf files.",
        b"Archive has duplicate or unsupported entries.",
        b"Archive cannot contain links.",
        b"Archive content length mismatch.",
        b"Malformed profile archive.",
        b"A profile already exists; import never overwrites.",
        b"Duplicate or unsupported configuration option.",
        b"Invalid config encoding/size.",
        b"Interface and at least one Peer required.",
        b"Incomplete Peer section.",
    }
    error = result.stderr.strip()
    if error.startswith(b"ERR:") and error[4:] in allowed_reasons:
        return False, error
    return False, b""


def execute(action: str, name: str, config: str | None = None,
            revision: str | None = None) -> OperationResult:
    if action not in {"install", "up", "down", "replace", "delete"}:
        return OperationResult(False, "Invalid privileged request.")
    if not valid_interface(name):
        return OperationResult(False, "Invalid profile name.")
    if action in {"install", "replace"} and config is None:
        return OperationResult(False, "Profile content missing.")
    if action not in {"install", "replace"} and (config is not None or revision is not None):
        return OperationResult(False, "Unexpected profile data.")
    if action == "replace":
        if revision is None or len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            return OperationResult(False, "Invalid revision.")
        payload = revision.encode("ascii") + b"\n" + config.encode("utf-8")
    else:
        payload = config.encode("utf-8") if config is not None else b""
    ok, output = _invoke(action, name, payload)
    expected = {"install": b"OK:installed", "replace": b"OK:replaced", "up": b"OK:up", "down": b"OK:down", "delete": b"OK:deleted"}[action]
    if ok and output.strip() == expected:
        return OperationResult(True, f"{name}: {action} completed.")
    reason = output.removeprefix(b"ERR:").decode("ascii") if output.startswith(b"ERR:") else ""
    return OperationResult(False, reason or "Operation unavailable, cancelled or rejected. Check authorization and the system journal.")


def list_system_profiles() -> InventoryResult:
    ok, output = _invoke("list", "all")
    if not ok or not output.startswith(b"OK:list\n"):
        return InventoryResult(False, "System profile inventory requires Polkit authorization.")
    try:
        entries = output.decode("ascii").splitlines()[1:]
    except UnicodeDecodeError:
        return InventoryResult(False, "Invalid system inventory.")
    names = tuple(sorted({s for s in entries if valid_interface(s)}))
    return InventoryResult(True, "System profiles loaded.", names)


def read_profile(name: str) -> ConfigResult:
    if not valid_interface(name):
        return ConfigResult(False, "Invalid interface name.")
    ok, output = _invoke("read", name)
    if not ok or not output.startswith(b"OK:read\n"):
        reason = output.removeprefix(b"ERR:").decode("ascii") if output.startswith(b"ERR:") else "Read requires Polkit; verify this is a regular root-owned configuration (no symlink or non-root write permissions)."
        return ConfigResult(False, reason, name)
    raw = output[len(b"OK:read\n"):]
    try:
        content = raw.decode("utf-8")
    except UnicodeError:
        return ConfigResult(False, "This profile cannot be displayed as UTF-8.", name)
    return ConfigResult(True, "Profile loaded.", name, content, hashlib.sha256(raw).hexdigest())

def read_bundle() -> BundleResult:
    """One strict Polkit grant yields all root-owned native configs as a ZIP.

    Raw configuration bytes are never logged or included in a dataclass repr.
    """
    ok, result = _invoke("bundle", "all")
    marker = b"OK:bundle\n"
    if ok and result.startswith(marker) and len(result) <= MAX_BUNDLE + len(marker):
        return BundleResult(True, "Native profile archive authorized.", result[len(marker):])
    reason = result.removeprefix(b"ERR:").decode("ascii") if result.startswith(b"ERR:") else ""
    return BundleResult(False, reason or "Cannot read all native profiles. Check Polkit and file permissions.")


def install_bundle(data: bytes) -> OperationResult:
    """Install all validated, previously absent profiles in a single transaction."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_BUNDLE:
        return OperationResult(False, "Invalid or oversized profile archive.")
    ok, result = _invoke("install-bundle", "all", data)
    if ok and result.startswith(b"OK:imported:"):
        count = result[len(b"OK:imported:"):].strip()
        if count.isdigit() and 0 < int(count) <= 100:
            return OperationResult(True, f"Imported {int(count)} new native profiles.")
    reason = result.removeprefix(b"ERR:").decode("ascii") if result.startswith(b"ERR:") else ""
    return OperationResult(False, reason or "Backup import rejected. Only new, supported native profiles are accepted.")
