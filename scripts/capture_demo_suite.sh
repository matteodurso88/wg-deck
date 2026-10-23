#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "WG Deck environment missing; run bash scripts/setup_env.sh" >&2
  exit 2
fi

# Deterministic offscreen Qt demo; never connects, imports or exports real VPNs.
exec env -u PYTHONPATH QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1 \
  "$PWD/.venv/bin/python" scripts/capture_demo_suite.py "$@"
