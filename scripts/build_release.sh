#!/usr/bin/env bash
# Local-first Debian-only release candidate build.
# WG Deck no longer distributes Python wheel or sdist as GitHub Release assets.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -x .venv/bin/python ]] || {
  echo "First run bash scripts/setup_env.sh to prepare the local quality gate." >&2
  exit 2
}

bash scripts/local_gate.sh
bash packaging/debian/build.sh
bash packaging/debian/test_deb.sh

echo "Debian release candidate ready under dist/ (not published)."
