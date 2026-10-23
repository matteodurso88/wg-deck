"""Local WireGuard key generation, never logged and never needing root."""
from __future__ import annotations

import base64
import binascii
import shutil
import subprocess


class KeyGenerationError(RuntimeError):
    pass


def _valid_key(key: str) -> bool:
    try:
        return len(base64.b64decode(key, validate=True)) == 32
    except (binascii.Error, ValueError):
        return False


def generate_keypair() -> tuple[str, str]:
    wg = shutil.which("wg")
    if not wg:
        raise KeyGenerationError("wireguard-tools (wg) is not installed.")
    try:
        private_result = subprocess.run(
            (wg, "genkey"), capture_output=True, check=False, timeout=8
        )
        if private_result.returncode:
            raise KeyGenerationError("WireGuard key generation failed.")
        private = private_result.stdout.decode("ascii").strip()
        if not _valid_key(private):
            raise KeyGenerationError("WireGuard generated an invalid key.")
        public_result = subprocess.run(
            (wg, "pubkey"), input=(private + "\n").encode("ascii"),
            capture_output=True, check=False, timeout=8
        )
        if public_result.returncode:
            raise KeyGenerationError("Unable to derive public key.")
        public = public_result.stdout.decode("ascii").strip()
        if not _valid_key(public):
            raise KeyGenerationError("Invalid derived public key.")
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        raise KeyGenerationError("WireGuard key generation unavailable.") from None
    return private, public
