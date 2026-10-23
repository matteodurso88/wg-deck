#!/usr/bin/env bash
# Build inspected Python distributions locally. Does not publish or install root helpers.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

[[ -x .venv/bin/python ]] || { echo "Run bash scripts/setup_env.sh first" >&2; exit 2; }
command -v uv >/dev/null 2>&1 || { echo "uv not installed" >&2; exit 2; }
bash scripts/local_gate.sh
uv pip install --python .venv/bin/python build
rm -rf dist/
.venv/bin/python -m build

.venv/bin/python - <<'PY'
from pathlib import Path
from tarfile import open as tar_open
from zipfile import ZipFile
dist = Path("dist")
wheels = list(dist.glob("wg_deck-1.0.0-*.whl"))
sources = list(dist.glob("wg_deck-1.0.0.tar.gz"))
assert len(wheels) == len(sources) == 1, "Expected one wheel and one sdist"
with ZipFile(wheels[0]) as package:
    paths = package.namelist()
    required = (
        "wg-deck-logo-dark.svg",
        "wg-deck-logo-light.svg",
        "wg-deck-symbol-dark.svg",
        "wg-deck-symbol-light.svg",
        "wg-deck-app.svg",
        "matt88-logo-light.svg",
        "matt88-logo-dark.svg",
    )
    for name in required:
        assert any(item.endswith("/assets/brand/" + name) for item in paths), name
    assert not any(item.endswith((".conf", ".key", ".pem", ".p12")) for item in paths)
    assert not any(item.startswith("privileged/") for item in paths)
print("Wheel SVG inclusion and secret-file extension checks: PASS")
with tar_open(sources[0], "r:gz") as source_archive:
    names = [name.split("/", 1)[-1] for name in source_archive.getnames()]
    needed = (
        "scripts/install_helper.sh",
        "scripts/uninstall_helper.sh",
        "scripts/install_desktop.sh",
        "scripts/capture_demo_suite.sh",
        "privileged/wgdeck_helper.py",
        "privileged/org.matt88.wgdeck.policy",
        "privileged/org.matt88.wgdeck.connection.policy",
        "privileged/org.matt88.wgdeck.read.policy",
        "privileged/wg-deck-inventory.service",
        "privileged/wg-deck-inventory.path",
        "privileged/wg-deck-inventory.timer",
        "docs/en/INSTALL.md",
        "docs/it/INSTALL.md",
        "docs/PROVENANCE.md",
        "MANIFEST.in",
    )
    missing = [item for item in needed if item not in names]
    assert not missing, f"sdist is incomplete; missing: {missing}"
    assert not any(item.endswith((".conf", ".key", ".pem", ".p12")) for item in names)
    assert "scripts/render_mock.py" not in names
print("Source distribution includes installers, Polkit/systemd and bilingual docs: PASS")
PY

(cd dist && sha256sum *.whl *.tar.gz > SHA256SUMS)
echo "Release candidates and checksums under dist/ (not published)."
