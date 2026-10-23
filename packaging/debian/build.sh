#!/usr/bin/env bash
# Build a distribution-managed, offline-installable Debian package.
# No sudo, no host installation, no network traffic, no WireGuard operations.
set -euo pipefail
cd "$(dirname "$0")/../.."
export LC_ALL=C
umask 022

for command in dpkg-deb python3 install; do
  command -v "$command" >/dev/null || { echo "Required build command unavailable: $command" >&2; exit 2; }
done

version="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Unexpected version" >&2; exit 2; }
output="$PWD/dist"
mkdir -p "$output"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/lib/python3/dist-packages" \
  "$stage/usr/lib/wg-deck" "$stage/usr/lib/systemd/system" \
  "$stage/usr/share/polkit-1/actions" \
  "$stage/usr/share/applications" "$stage/usr/share/icons/hicolor/scalable/apps" \
  "$stage/usr/share/doc/wg-deck/en" "$stage/usr/share/doc/wg-deck/it"

# WG Deck itself is pure Python; CPython/PySide6/Qt are APT-managed.
# Architecture all can use the distro's amd64 or arm64 bindings transparently.
cp -a src/wg_deck "$stage/usr/lib/python3/dist-packages/"
find "$stage/usr/lib/python3/dist-packages/wg_deck" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$stage/usr/lib/python3/dist-packages/wg_deck" -type f -name '*.pyc' -delete

# Explicit narrow mapping from developer root-owned /usr/local helpers
# to the FHS /usr/lib/wg-deck location owned by dpkg. Never install there
# from the user-writable repository or from a package maintainer hook.
python3 - "$stage" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
replacements = {
    root / "usr/lib/python3/dist-packages/wg_deck/core/privileged.py": (
        ("/usr/local/libexec/", "/usr/lib/wg-deck/"),
    ),
    root / "usr/lib/python3/dist-packages/wg_deck/core/autostart.py": (
        ('Path(__file__).resolve().parents[3] / "scripts" / "run.sh"',
         'Path("/usr/bin/wg-deck")'),
        ('f\'Exec=/usr/bin/bash "{script}"\\n\'', 'f\'Exec="{script}"\\n\''),
        ('"TryExec=/usr/bin/bash\\n"', '"TryExec=/usr/bin/wg-deck\\n"'),
    ),
}
for filename, transforms in replacements.items():
    body = filename.read_text("utf-8")
    for old, new in transforms:
        if body.count(old) != 1:
            raise SystemExit(f"Packaging source contract changed: {filename.name}: {old}")
        body = body.replace(old, new)
    filename.write_text(body, encoding="utf-8")
PY

for entry in helper connection read inventory; do
  case "$entry" in
    helper) source_file=privileged/wgdeck_helper.py ;;
    connection) source_file=privileged/wgdeck_connection.py ;;
    read) source_file=privileged/wgdeck_read.py ;;
    inventory) source_file=privileged/wgdeck_inventory.py ;;
  esac
  install -m 0755 "$source_file" "$stage/usr/lib/wg-deck/wg-deck-$entry"
done
python3 - "$stage" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for filename in ("wg-deck-connection", "wg-deck-read"):
    item = root / "usr/lib/wg-deck" / filename
    text = item.read_text("utf-8")
    old = '/usr/local/libexec/wg-deck-helper'
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected root dispatcher source: {filename}")
    item.write_text(text.replace(old, '/usr/lib/wg-deck/wg-deck-helper'), encoding="utf-8")
for filename in (
    "org.matt88.wgdeck.policy",
    "org.matt88.wgdeck.connection.policy",
    "org.matt88.wgdeck.read.policy",
):
    src = Path("privileged") / filename
    dest = root / "usr/share/polkit-1/actions" / filename
    text = src.read_text("utf-8")
    old = "/usr/local/libexec/"
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected Polkit exec.path: {filename}")
    dest.write_text(text.replace(old, "/usr/lib/wg-deck/"), encoding="utf-8")
for extension in ("service", "timer", "path"):
    name = "wg-deck-inventory." + extension
    text = (Path("privileged") / name).read_text("utf-8")
    if extension == "service":
        old = "/usr/local/libexec/wg-deck-inventory"
        if text.count(old) != 1:
            raise SystemExit("Unexpected inventory service entrypoint")
        text = text.replace(old, "/usr/lib/wg-deck/wg-deck-inventory")
    (root / "usr/lib/systemd/system" / name).write_text(text, encoding="utf-8")
PY
chmod 0755 "$stage/usr/lib/wg-deck/"*
chmod 0644 "$stage/usr/share/polkit-1/actions/"*
chmod 0644 "$stage/usr/lib/systemd/system/"*

cat > "$stage/usr/bin/wg-deck" <<'PY'
#!/usr/bin/python3
"""System Python launcher; PySide6 is provided and updated by APT."""
from wg_deck.qt_app import main
if __name__ == "__main__":
    raise SystemExit(main())
PY
chmod 0755 "$stage/usr/bin/wg-deck"
install -m 0755 packaging/debian/wg-deck-setup.sh "$stage/usr/bin/wg-deck-setup"
install -m 0644 src/wg_deck/assets/brand/wg-deck-app.svg "$stage/usr/share/icons/hicolor/scalable/apps/wg-deck.svg"

cat > "$stage/usr/share/applications/org.matt88.wg-deck.desktop" <<'DESKTOP'
[Desktop Entry]
Version=1.0
Type=Application
Name=WG Deck
Comment=Native Linux WireGuard profile manager
Exec=/usr/bin/wg-deck
Icon=wg-deck
Terminal=false
Categories=Network;Utility;
StartupNotify=true
DESKTOP

for file in LICENSE NOTICE.md README.md README.it.md CHANGELOG.md; do
  install -m 0644 "$file" "$stage/usr/share/doc/wg-deck/$file"
done
for language in en it; do
  for file in docs/"$language"/*.md; do
    install -m 0644 "$file" "$stage/usr/share/doc/wg-deck/$language/$(basename "$file")"
  done
done
install -m 0755 packaging/debian/postrm "$stage/DEBIAN/postrm"
cat > "$stage/DEBIAN/control" <<EOF
Package: wg-deck
Version: $version
Section: net
Priority: optional
Architecture: all
Maintainer: WG Deck contributors <306640865+matteodurso88@users.noreply.github.com>
Depends: python3 (>= 3.12), python3-pyside6.qtwidgets (>= 6.10), python3-pyside6.qtsvg (>= 6.10), libegl1, wireguard-tools, iproute2, pkexec, systemd
Recommends: qt6-wayland
Homepage: https://github.com/matteodurso88/wg-deck
Description: Independent graphical WireGuard profile manager for Linux
 PySide6 desktop interface with separately authorized Polkit helpers.
 Native VPN configurations remain managed by the operating system.
 Installation never starts a VPN, changes routes or enables services.
EOF
# Refuse accidental inclusion of private material or stage build byproducts.
if find "$stage" \( -name '*.conf' -o -name '*.pem' -o -name '*.key' -o -name '.env' \) | grep -q .; then
  echo "Secrets or private configuration detected in package stage." >&2; exit 2
fi

destination="$output/wg-deck_${version}_all.deb"
dpkg-deb --root-owner-group --build "$stage" "$destination"
(cd "$output" && sha256sum "$(basename "$destination")" > SHA256SUMS)
echo "Created: $destination"
echo "No wheel/sdist produced or published; system installation remains separate."
