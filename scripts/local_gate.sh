#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="$PWD/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Environment missing. First run: bash scripts/setup_env.sh" >&2
  exit 2
fi

# Never hide a broken editable install using PYTHONPATH=src.
# The import and metadata checks must work exactly as the launcher invokes Python.
if ! env -u PYTHONPATH "$PYTHON" -c 'from importlib.metadata import version; import wg_deck; import PySide6; assert version("wg-deck")'; then
  echo "WG Deck is not installed in .venv. Run: bash scripts/setup_env.sh" >&2
  exit 2
fi

"$PYTHON" -m compileall -q src tests
"$PYTHON" -m py_compile privileged/wgdeck_helper.py privileged/wgdeck_inventory.py privileged/wgdeck_connection.py privileged/wgdeck_read.py
"$PYTHON" -c 'import xml.etree.ElementTree as ET; ET.parse("privileged/org.matt88.wgdeck.policy"); ET.parse("privileged/org.matt88.wgdeck.connection.policy"); ET.parse("privileged/org.matt88.wgdeck.read.policy")'
bash -n scripts/install_helper.sh scripts/uninstall_helper.sh scripts/install_desktop.sh scripts/uninstall_desktop.sh scripts/check_native_inventory.sh scripts/check_native_traffic.sh scripts/capture_demo_suite.sh scripts/build_release.sh packaging/debian/build.sh packaging/debian/test_deb.sh packaging/debian/wg-deck-setup.sh
sh -n packaging/debian/prerm packaging/debian/postinst packaging/debian/postrm
bash -n scripts/verify_installed_deb.sh
env -u PYTHONPATH "$PYTHON" -m unittest discover -s tests -v

echo "WG Deck candidate gate PASS (unit + security + Qt offscreen + SVG + helper syntax)."
echo "REAL wg-quick / Polkit operation and Dell GNOME/Wayland smoke remain PENDING."
