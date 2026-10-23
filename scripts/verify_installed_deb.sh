#!/usr/bin/env bash
# WG Deck local Ubuntu desktop acceptance preflight.
# Read-only. Never runs sudo, pkexec, wg-quick, or reads .conf contents.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "=== WG Deck Debian installed package ==="
installed="$(dpkg-query -W -f='${Version}' wg-deck 2>/dev/null || true)"
[[ "$installed" == "1.0.0-3" ]] || { echo "Expected 1.0.0-3; installed: ${installed:-none}" >&2; exit 2; }
echo "APT version: $installed"
command -v wg-deck >/dev/null || { echo "GUI launcher missing" >&2; exit 2; }

echo "=== Source and artifact ==="
[[ "$(git branch --show-current)" == "main" ]] || { echo "Switch to public main" >&2; exit 2; }
[[ -z "$(git status --porcelain)" ]] || { echo "Dirty Git working tree" >&2; exit 2; }
if ! upstream="$(git ls-remote origin refs/heads/main)"; then
  echo "Cannot verify GitHub main SHA" >&2; exit 2
fi
remote_sha="${upstream%%[[:space:]]*}"
[[ -n "$remote_sha" && "$remote_sha" == "$(git rev-parse HEAD)" ]] || {
  echo "Local main does not match published GitHub main" >&2; exit 2
}
echo "Source SHA: $remote_sha"
[[ -f dist/wg-deck_1.0.0-3_all.deb && -f dist/SHA256SUMS ]] || {
  echo "Local .deb/checksum not built" >&2; exit 2
}
(cd dist && sha256sum -c SHA256SUMS)

echo "=== Root-owned helper and systemd ==="
[[ "$(stat -c '%u:%a' /usr/lib/wg-deck/wg-deck-helper)" == "0:755" ]] || {
  echo "Unexpected helper ownership or mode" >&2; exit 2
}
for unit in wg-deck-inventory.path wg-deck-inventory.timer; do
  systemctl is-active --quiet "$unit" || { echo "$unit is not active" >&2; exit 2; }
done

echo "=== Unprivileged sanitized profile inventory ==="
python3 - <<'PY'
from wg_deck.core.system_profiles import read_native_names
names = read_native_names()
assert names is not None, "Read-only native inventory is not accessible"
print(f"Validated existing native profile names: {len(names)}")
if not names:
    print("Note: no profiles currently visible; check a known existing profile from GUI")
PY
snapshot="/run/wg-deck-profiles.list"
[[ -f "$snapshot" && ! -L "$snapshot" ]] || { echo "Missing/unsafe native snapshot" >&2; exit 2; }
[[ "$(stat -c '%u' "$snapshot")" == "0" ]] || { echo "Native snapshot is not root-owned" >&2; exit 2; }

echo "LOCAL DEBIAN INSTALL/INVENTORY PREFLIGHT PASS"
echo "STILL MANUAL: GNOME launcher, tray, Polkit read and disposable VPN operation."
