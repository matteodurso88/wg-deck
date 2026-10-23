#!/usr/bin/python3
"""WG Deck privileged helper: uniform profile management.

Install this file root-owned in /usr/local/libexec, never execute it from
a mutable checkout or virtualenv as root. Standalone Python stdlib only.
Polkit authorizes each call via pkexec. No arbitrary paths or shell commands.
"""
from __future__ import annotations

import base64
import hashlib
import tempfile
import binascii
import fcntl
import io
import zipfile
import ipaddress
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path("/etc/wireguard")
RUNTIME = Path("/run/wg-deck")
MAX_CONFIG = 64 * 1024
MAX_BUNDLE = 2 * 1024 * 1024
MAX_BUNDLE_PROFILES = 100
NAME = re.compile(r"[A-Za-z0-9_=+.-]{1,15}\Z")
IFACE = {"privatekey", "address", "listenport", "dns", "mtu"}
PEER = {"publickey", "presharedkey", "endpoint", "allowedips", "persistentkeepalive"}
ACTIONS = {"install", "up", "down", "read", "replace", "list", "delete", "bundle", "install-bundle"}


class Rejected(Exception):
    pass


def reject(msg: str) -> None:
    raise Rejected(msg)


def safe_name(name: str) -> str:
    if not NAME.fullmatch(name) or name in {".", ".."}:
        reject("Invalid interface identifier.")
    return name


def check_key(s: str) -> None:
    try:
        raw = base64.b64decode(s, validate=True)
    except (ValueError, binascii.Error):
        reject("Invalid WireGuard key.")
    if len(raw) != 32 or base64.b64encode(raw).decode() != s:
        reject("Invalid WireGuard key.")


def check_ips(value: str, *, interface: bool) -> None:
    fields = [part.strip() for part in value.split(",")]
    if not fields or not all(fields):
        reject("Invalid address list.")
    try:
        for item in fields:
            if interface:
                ipaddress.ip_interface(item)
            else:
                ipaddress.ip_network(item, strict=False)
    except ValueError:
        reject("Invalid address list.")


def valid_config(data: bytes) -> None:
    """Narrow allowlist: no hooks, commands, unknown directives or continuation."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        reject("Config is not valid UTF-8.")
    if len(data) > MAX_CONFIG or not text.endswith("\n") or "\x00" in text:
        reject("Invalid config encoding/size.")
    section = None
    interface_seen = 0
    peer_seen = 0
    seen = set()
    previous_peer: set[str] | None = None
    interface_fields: set[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line == "[Interface]":
            if interface_seen or peer_seen:
                reject("Only one Interface section is allowed, before Peers.")
            interface_seen += 1
            section = "interface"
            seen = set()
            interface_fields = seen
            continue
        if line == "[Peer]":
            if interface_seen != 1:
                reject("Peer requires Interface.")
            if previous_peer is not None and not {"publickey", "allowedips"} <= previous_peer:
                reject("Incomplete Peer section.")
            section = "peer"
            peer_seen += 1
            seen = set()
            previous_peer = seen
            continue
        if not section or "=" not in line:
            reject("Unsupported configuration syntax.")
        key, value = (s.strip() for s in line.split("=", 1))
        k = key.casefold()
        allowed = IFACE if section == "interface" else PEER
        if k not in allowed or k in seen:
            reject("Duplicate or unsupported configuration option.")
        if not value or any(c in value for c in "\r\n\\#;"):
            reject("Invalid field value.")
        seen.add(k)
        if k in {"privatekey", "publickey", "presharedkey"}:
            check_key(value)
        elif k in {"address", "allowedips"}:
            check_ips(value, interface=k == "address")
        elif k == "dns":
            for dns in value.split(","):
                try:
                    ipaddress.ip_address(dns.strip())
                except ValueError:
                    reject("DNS must contain only IP addresses.")
        elif k == "endpoint":
            if any(c.isspace() for c in value) or len(value) > 260:
                reject("Invalid endpoint.")
            if value.startswith("["):
                m = re.fullmatch(r"\[([0-9a-fA-F:.]+)\]:(\d{1,5})", value)
                if not m:
                    reject("Invalid endpoint.")
                try:
                    ipaddress.IPv6Address(m.group(1))
                except ValueError:
                    reject("Invalid endpoint.")
            else:
                m = re.fullmatch(r"[a-zA-Z0-9.-]+:(\d{1,5})", value)
                if not m:
                    reject("Invalid endpoint.")
            port = int(m.group(2) if value.startswith("[") else m.group(1))
            if not 1 <= port <= 65535:
                reject("Invalid endpoint.")
        elif k in {"listenport", "persistentkeepalive", "mtu"}:
            if not value.isascii() or not value.isdecimal():
                reject("Invalid numeric parameter.")
            number = int(value)
            if not (0 <= number <= 65535) or (k == "mtu" and not 576 <= number <= 9000):
                reject("Invalid numeric parameter.")
    if interface_seen != 1 or peer_seen < 1:
        reject("Interface and at least one Peer required.")
    if interface_fields is None or not {"privatekey", "address"} <= interface_fields:
        reject("Incomplete Interface section.")
    if previous_peer is None or not {"publickey", "allowedips"} <= previous_peer:
        reject("Incomplete Peer section.")


def secure_directory(path: Path, mode: int = 0o700) -> None:
    if path.is_symlink():
        reject("Unsafe directory link.")
    if not path.exists():
        path.mkdir(mode=mode)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        reject("Unsafe directory ownership/permissions.")


def secure_file(path: Path) -> bytes:
    # O_NOFOLLOW and fd metadata stop symlink races between stat and open.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            # Root-owned system profiles may be group/world readable if
            # created manually. Non-root WRITE permissions remain forbidden.
            # This is never a reason to categorize GUI and Bash profiles.
            reject("Unsafe config owner or writable permissions.")
        if info.st_size > MAX_CONFIG:
            reject("Configuration oversized.")
        with os.fdopen(fd, "rb", closefd=False) as source:
            data = source.read(MAX_CONFIG + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_CONFIG:
        reject("Configuration oversized.")
    return data


def run(*args: str) -> None:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            timeout=40,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        reject("WireGuard command failed or timed out.")
    if result.returncode != 0:
        # wg-quick output may contain networking and other private metadata.
        reject("WireGuard operation failed. Consult the local system journal.")


def is_up(name: str) -> bool:
    result = subprocess.run(
        ("/usr/sbin/ip" if Path("/usr/sbin/ip").is_file() else "/usr/bin/ip", "link", "show", "dev", name),
        check=False, capture_output=True, timeout=5,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return result.returncode == 0


def systemd_unit(name: str) -> str:
    safe_name(name)
    return f"wg-quick@{name}.service"


def systemd_is(name: str, check: str) -> bool:
    if check not in {"is-active", "is-enabled"}:
        return False
    try:
        result = subprocess.run(
            ("/usr/bin/systemctl", check, "--quiet", systemd_unit(name)),
            check=False, capture_output=True, timeout=5,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def is_wireguard(name: str) -> bool:
    """Do not call wg-quick down on an unrelated Linux interface."""
    try:
        result = subprocess.run(
            ("/usr/bin/wg", "show", name, "listen-port"),
            check=False, capture_output=True, timeout=5,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def interface_index(name: str) -> int | None:
    """Kernel ifindex detects if a foreign actor recreated an interface."""
    safe_name(name)
    try:
        value = int((Path("/sys/class/net") / name / "ifindex").read_text().strip())
        return value if value > 0 else None
    except (OSError, ValueError):
        return None


def handle(action: str, name: str, payload: bytes = b"") -> None:
    """Apply identical rules to every root-owned profile, regardless of origin."""
    if action not in ACTIONS:
        reject("Unsupported operation.")
    if action not in {"list", "bundle", "install-bundle"}:
        safe_name(name)
    elif name != "all":
        reject("Invalid aggregate profile request.")
    if os.geteuid() != 0:
        reject("Helper requires authenticated root execution.")
    secure_directory(ROOT)
    secure_directory(RUNTIME)
    lock_path = RUNTIME / ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if action == "bundle":
            # Single Polkit authorization reads all native configs at a single
            # point-in-time. Fail CLOSED rather than silently skip any .conf.
            candidates = sorted(ROOT.glob("*.conf"), key=lambda p: p.name.casefold())
            if not candidates or len(candidates) > MAX_BUNDLE_PROFILES:
                reject("No profiles or too many profiles for a backup.")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
                for candidate in candidates:
                    safe_name(candidate.stem)
                    # secure_file rejects symlinks, nonroot write and oversized files.
                    content = secure_file(candidate)
                    archive.writestr(candidate.name, content, compress_type=zipfile.ZIP_STORED)
                    if buffer.tell() > MAX_BUNDLE:
                        reject("Profile archive exceeds the size limit.")
            payload_archive = buffer.getvalue()
            if len(payload_archive) > MAX_BUNDLE:
                reject("Profile archive exceeds the size limit.")
            sys.stdout.buffer.write(b"OK:bundle\n" + payload_archive)
            return

        if action == "install-bundle":
            # Strict all-or-nothing import; never overwrite an existing name.
            if not payload or len(payload) > MAX_BUNDLE:
                reject("Invalid or oversized profile archive.")
            try:
                with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                    entries = archive.infolist()
                    if not 1 <= len(entries) <= MAX_BUNDLE_PROFILES:
                        reject("Invalid profile archive entry count.")
                    prepared = []
                    names = set()
                    total = 0
                    for entry in entries:
                        name = entry.filename
                        if not name.endswith(".conf") or name != Path(name).name:
                            reject("Archive must contain only native .conf files.")
                        safe_name(name[:-5])
                        if name in names or entry.is_dir() or entry.compress_type != zipfile.ZIP_STORED:
                            reject("Archive has duplicate or unsupported entries.")
                        # Do not accept symlinks (POSIX ZIP external attributes).
                        if ((entry.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                            reject("Archive cannot contain links.")
                        names.add(name)
                        total += entry.file_size
                        if entry.file_size > MAX_CONFIG or total > MAX_BUNDLE:
                            reject("Profile archive exceeds the size limit.")
                        content = archive.read(entry)
                        if len(content) != entry.file_size:
                            reject("Archive content length mismatch.")
                        # Imported configs may later run as root via wg-quick;
                        # the existing strict subset disallows shell hooks.
                        valid_config(content)
                        prepared.append((ROOT / name, content))
            except (zipfile.BadZipFile, EOFError, RuntimeError, ValueError):
                reject("Malformed profile archive.")
            if any(path.exists() or path.is_symlink() for path, _ in prepared):
                reject("A profile already exists; import never overwrites.")
            created = []
            try:
                for target, content in prepared:
                    descriptor = os.open(
                        target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                    )
                    created.append(target)
                    with os.fdopen(descriptor, "wb") as out:
                        out.write(content)
                        out.flush()
                        os.fsync(out.fileno())
                directory_fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except Exception:
                # A failed import must not leave a half-installed selection.
                for installed in created:
                    installed.unlink(missing_ok=True)
                raise
            print(f"OK:imported:{len(created)}")
            return

        if action == "list":
            # One explicit Polkit authorization; names only, no secrets.
            print("OK:list")
            for candidate in sorted(ROOT.glob("*.conf")):
                if candidate.is_symlink() or not NAME.fullmatch(candidate.stem):
                    continue
                try:
                    secure_file(candidate)
                except (Rejected, OSError):
                    continue
                print(candidate.stem)
            return

        path = ROOT / f"{name}.conf"
        if action == "install":
            if not payload or len(payload) > MAX_CONFIG:
                reject("Invalid new profile.")
            valid_config(payload)
            # No overwrites, regardless of creator.
            try:
                new_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                reject("Profile already exists. No overwrites are allowed.")
            try:
                with os.fdopen(new_fd, "wb") as out:
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
            except Exception:
                path.unlink(missing_ok=True)
                raise
            print("OK:installed")
            return

        original = secure_file(path)
        if action == "read":
            # Authorized by Polkit, bounded output sent only to calling process.
            sys.stdout.buffer.write(b"OK:read\n" + original)
            return

        if action == "delete":
            # Never delete an active or systemd-enabled tunnel. Back up first.
            if is_up(name):
                reject("Disconnect the active tunnel before deleting the profile.")
            if systemd_is(name, "is-enabled") or systemd_is(name, "is-active"):
                reject("Disable the wg-quick systemd unit before deleting its profile.")
            backup_dir = ROOT / ".wg-deck-backups"
            secure_directory(backup_dir)
            digest = hashlib.sha256(original).hexdigest()
            backup = backup_dir / f"{name}-deleted-{digest[:24]}.conf"
            if backup.exists():
                if secure_file(backup) != original:
                    reject("An existing backup does not match; deletion cancelled.")
            else:
                backup_fd = os.open(
                    backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                try:
                    with os.fdopen(backup_fd, "wb") as out:
                        out.write(original)
                        out.flush()
                        os.fsync(out.fileno())
                except Exception:
                    backup.unlink(missing_ok=True)
                    raise
            if (secure_file(path) != original or is_up(name)
                    or systemd_is(name, "is-enabled")
                    or systemd_is(name, "is-active")):
                reject("Profile changed or reactivated; deletion cancelled.")
            path.unlink()
            dir_fd = os.open(ROOT, os.O_DIRECTORY | os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            print("OK:deleted")
            return

        if action == "replace":
            if is_up(name):
                reject("Disconnect the active tunnel before saving changes.")
            if b"\n" not in payload:
                reject("Missing revision guard.")
            digest, revised = payload.split(b"\n", 1)
            if (len(digest) != 64 or
                    any(ch not in b"0123456789abcdef" for ch in digest)):
                reject("Invalid revision guard.")
            if hashlib.sha256(original).hexdigest().encode("ascii") != digest:
                reject("Profile changed outside WG Deck; reload before saving.")
            valid_config(revised)
            # Backups are common for ALL profiles; no ownership labels.
            backup_dir = ROOT / ".wg-deck-backups"
            secure_directory(backup_dir)
            backup_name = name + "-" + digest.decode("ascii")[:20] + ".conf"
            backup = backup_dir / backup_name
            if not backup.exists():
                backup_fd = os.open(
                    backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                with os.fdopen(backup_fd, "wb") as out:
                    out.write(original)
                    out.flush()
                    os.fsync(out.fileno())
            staged_fd, staged_path = tempfile.mkstemp(prefix=".wgdeck-", dir=ROOT)
            try:
                os.fchmod(staged_fd, 0o600)
                with os.fdopen(staged_fd, "wb") as out:
                    out.write(revised)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(staged_path, path)
                dir_fd = os.open(ROOT, os.O_DIRECTORY | os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            finally:
                if os.path.exists(staged_path):
                    os.unlink(staged_path)
            print("OK:replaced")
            return

        if action == "up":
            if is_up(name):
                reject("Interface is already active.")
            if systemd_is(name, "is-enabled"):
                run("/usr/bin/systemctl", "start", systemd_unit(name))
            else:
                run("/usr/bin/wg-quick", "up", name)
            if not is_up(name):
                reject("Interface did not appear after activation.")
            print("OK:up")
        elif action == "down":
            if not is_up(name):
                reject("Interface is not active.")
            if not is_wireguard(name):
                reject("Refusing to disconnect a non-WireGuard interface.")
            if systemd_is(name, "is-active"):
                run("/usr/bin/systemctl", "stop", systemd_unit(name))
            else:
                run("/usr/bin/wg-quick", "down", name)
            if is_up(name):
                reject("Interface still exists after disconnect.")
            print("OK:down")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main() -> int:
    if len(sys.argv) != 3:
        print("ERR:Invalid command shape", file=sys.stderr)
        return 2
    action, name = sys.argv[1:]
    try:
        payload = b""
        if action in {"install", "replace", "install-bundle"}:
            # Bounded stdin, not process arguments; never printed or logged.
            limit = MAX_BUNDLE if action == "install-bundle" else MAX_CONFIG + 128
            payload = sys.stdin.buffer.read(limit + 1)
        handle(action, name, payload)
        return 0
    except (Rejected, OSError, subprocess.TimeoutExpired) as ex:
        if isinstance(ex, Rejected):
            print(f"ERR:{ex}", file=sys.stderr)
        else:
            print("ERR:Privileged operation unavailable.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
