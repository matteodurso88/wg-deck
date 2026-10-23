#!/usr/bin/env bash
# Optional privacy restriction or administrative disable. APT now activates
# safe, read-only inventory automatically at installation (no setup needed).
# Never creates/deletes a VPN config or starts/stops an interface.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo "Run with sudo (e.g. sudo wg-deck-setup --enable-inventory USER)." >&2; exit 2; }

case "$*" in
  "--disable-inventory")
    systemctl disable --now wg-deck-inventory.timer wg-deck-inventory.path
    echo "WG Deck inventory publisher disabled. VPN connections unaffected."
    ;;
  *)
    [[ "$#" -eq 2 && ( "$1" == "--enable-inventory" || "$1" == "--restrict-inventory" ) ]] || {
      echo "Usage: sudo wg-deck-setup --restrict-inventory USER | --disable-inventory" >&2
      exit 2
    }
    username="$2"
    [[ "$username" =~ ^[a-z_][a-z0-9_.-]*[$]?$ ]] || {
      echo "Invalid local username" >&2; exit 2
    }
    account="$(getent passwd "$username")"
    [[ -n "$account" ]] || { echo "User not found" >&2; exit 2; }
    gid="$(id -g "$username")"
    [[ "$gid" =~ ^[0-9]+$ && "$gid" -gt 0 ]] || { echo "Unsafe user group" >&2; exit 2; }
    # Restrict the otherwise world-readable, non-secret metadata to one primary group.
    # Atomic root-owned replacement prevents following a malicious symlink.
    config="$(mktemp /etc/.wg-deck-reader-gid.XXXXXXXX)"
    trap 'rm -f "$config"' EXIT
    printf '%s\n' "$gid" > "$config"
    chown root:root "$config"
    chmod 0600 "$config"
    mv -fT "$config" /etc/wg-deck-reader-gid
    trap - EXIT
    systemctl daemon-reload
    systemctl enable --now wg-deck-inventory.path wg-deck-inventory.timer
    systemctl start wg-deck-inventory.service
    echo "Read-only inventory visibility restricted to primary group of $username (GID $gid)."
    echo "No WireGuard interface was started or stopped."
    ;;
esac
