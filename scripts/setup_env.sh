#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found. Install/configure uv before setting up WG Deck." >&2
  exit 127
fi

if [[ -x .venv/bin/python ]]; then
  if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
    echo "The existing .venv does not use Python 3.12." >&2
    echo "To recreate only the local virtualenv: uv venv --clear --python 3.12 .venv" >&2
    echo "Then rerun: bash scripts/setup_env.sh" >&2
    exit 2
  fi
else
  uv venv --python 3.12 .venv
fi

uv pip install --python .venv/bin/python -e .
# Verify the editable install, not merely the repository's src/ directory.
env -u PYTHONPATH .venv/bin/python -c 'import sys, PySide6, wg_deck; from importlib.metadata import version; dist=version("wg-deck"); print(f"Python: {sys.version.split()[0]} | PySide6: {PySide6.__version__} | WG Deck: {dist}")'
echo "Environment ready: use .venv/bin/python (no shell activation required)."
