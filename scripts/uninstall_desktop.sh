#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ "$(id -u)" -ne 0 ]] || { echo "Run as a normal desktop user." >&2; exit 2; }

# Disable only our own managed login entry before removing desktop integration.
# Refuse to remove user-customized entries; never follow symlinks.
if [[ -x "$PWD/.venv/bin/python" ]]; then
  env -u PYTHONPATH "$PWD/.venv/bin/python" - <<'PY'
from wg_deck.core.autostart import AutostartError, set_enabled

try:
    set_enabled(False)
except AutostartError as exc:
    raise SystemExit(f"Autostart must be disabled manually before uninstall: {exc}")
PY
else
  echo "Python environment unavailable: turn off autostart in Settings before removing the project." >&2
fi

rm -f "$HOME/.local/share/applications/org.matt88.wg-deck.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/wg-deck.svg"
echo "WG Deck desktop launcher and icon removed. VPN profiles were not changed."
