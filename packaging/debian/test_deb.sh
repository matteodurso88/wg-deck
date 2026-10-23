#!/usr/bin/env bash
# Offline, unprivileged package layout verification; never installs on host.
set -euo pipefail
cd "$(dirname "$0")/../.."
deb="$(find dist -maxdepth 1 -type f -name 'wg-deck_*_all.deb' -print -quit)"
[[ -f "$deb" ]] || { echo "Debian package missing" >&2; exit 2; }
[[ "$(dpkg-deb -f "$deb" Package)" == "wg-deck" ]]
[[ "$(dpkg-deb -f "$deb" Architecture)" == "all" ]]
[[ "$(dpkg-deb -f "$deb" Version)" == "1.0.0-3" ]]
deps="$(dpkg-deb -f "$deb" Depends)"
grep -q 'python3-pyside6.qtwidgets' <<< "$deps"
grep -q 'python3-pyside6.qtsvg' <<< "$deps"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
dpkg-deb -x "$deb" "$scratch"
dpkg-deb -e "$deb" "$scratch/DEBIAN"
for file in \
  usr/bin/wg-deck usr/bin/wg-deck-setup \
  usr/lib/python3/dist-packages/wg_deck/qt_app.py \
  usr/lib/wg-deck/wg-deck-helper usr/lib/wg-deck/wg-deck-connection \
  usr/lib/wg-deck/wg-deck-read usr/lib/wg-deck/wg-deck-inventory \
  usr/lib/systemd/system/wg-deck-inventory.service \
  usr/share/polkit-1/actions/org.matt88.wgdeck.policy \
  usr/share/polkit-1/actions/org.matt88.wgdeck.read.policy \
  usr/share/polkit-1/actions/org.matt88.wgdeck.connection.policy \
  usr/share/applications/org.matt88.wg-deck.desktop \
  usr/share/icons/hicolor/scalable/apps/wg-deck.svg \
  usr/share/doc/wg-deck/LICENSE usr/share/doc/wg-deck/copyright usr/share/doc/wg-deck/en/INSTALL.md \
  usr/share/doc/wg-deck/it/INSTALL.md; do
  [[ -f "$scratch/$file" ]] || { echo "Missing package file: $file" >&2; exit 2; }
done
[[ ! -e "$scratch/etc/wireguard" ]] || { echo "Package would write native profiles" >&2; exit 2; }
[[ ! -e "$scratch/etc/wg-deck-reader-gid" ]] || { echo "Unexpected user-specific reader-group state bundled" >&2; exit 2; }
[[ -f "$scratch/DEBIAN/postinst" ]] || { echo "Missing automatic installer configuration" >&2; exit 2; }
[[ -f "$scratch/DEBIAN/prerm" ]] || { echo "Missing safe pre-removal hook" >&2; exit 2; }
grep -q 'systemctl disable --now wg-deck-inventory.path wg-deck-inventory.timer' "$scratch/DEBIAN/prerm"
grep -q 'systemctl enable --now wg-deck-inventory.path wg-deck-inventory.timer' "$scratch/DEBIAN/postinst"
grep -q 'systemctl start wg-deck-inventory.service' "$scratch/DEBIAN/postinst"
grep -q '/usr/lib/wg-deck/wg-deck-helper' "$scratch/usr/share/polkit-1/actions/org.matt88.wgdeck.policy"
grep -q '/usr/lib/wg-deck/wg-deck-inventory' "$scratch/usr/lib/systemd/system/wg-deck-inventory.service"
grep -q '/usr/lib/wg-deck/wg-deck-helper' "$scratch/usr/lib/python3/dist-packages/wg_deck/core/privileged.py"
if grep -R -l '/usr/local/libexec/wg-deck' "$scratch/usr/lib/wg-deck" "$scratch/usr/share/polkit-1/actions" "$scratch/usr/lib/python3/dist-packages/wg_deck/core/privileged.py"; then
  echo "Old helper prefix in installed package" >&2; exit 2
fi
if grep -qE '/etc/wireguard|wg-quick (up|down)' "$scratch/DEBIAN/postrm"; then
  echo "Package maintainer script could touch VPNs" >&2; exit 2
fi
python3 - "$scratch" <<'PY'
from pathlib import Path
import sys, ast
root = Path(sys.argv[1])
for file in (root/"usr/lib/python3/dist-packages/wg_deck").rglob("*.py"):
    ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
for file in (root/"usr/lib/wg-deck").glob("wg-deck-*"):
    ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
PY
bash -n "$scratch/usr/bin/wg-deck-setup"
sh -n "$scratch/DEBIAN/prerm"
sh -n "$scratch/DEBIAN/postinst"
sh -n "$scratch/DEBIAN/postrm"
if grep -E 'wg-quick (up|down)|wg setconf' "$scratch/DEBIAN/prerm"; then
  echo "Pre-removal hook must not manipulate VPNs" >&2; exit 2
fi
if grep -E 'wg-quick (up|down)|wg setconf' "$scratch/DEBIAN/postinst"; then
  echo "Post-install must not manipulate VPNs" >&2; exit 2
fi
(cd dist && sha256sum -c SHA256SUMS)
echo "DEB PACKAGE SAFETY/LAYOUT: PASS (no installation performed)"
