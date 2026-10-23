#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ "$(id -u)" -ne 0 ]] || { echo "Run as a normal desktop user." >&2; exit 2; }
[[ -x "$PWD/.venv/bin/python" ]] || { echo "First run bash scripts/setup_env.sh" >&2; exit 2; }
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
install -m 0644 src/wg_deck/assets/brand/wg-deck-app.svg "$HOME/.local/share/icons/hicolor/scalable/apps/wg-deck.svg"
cat > "$HOME/.local/share/applications/org.matt88.wg-deck.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=WG Deck
Comment=Native Linux WireGuard profile manager · matt88.it
Exec=$PWD/scripts/run.sh
Icon=wg-deck
Terminal=false
Categories=Network;Utility;
StartupNotify=true
EOF
chmod 0644 "$HOME/.local/share/applications/org.matt88.wg-deck.desktop"
echo "WG Deck desktop launcher and canonical app icon installed for user $(id -un)."
