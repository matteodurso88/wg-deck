#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="$PWD/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Environment missing. Run: bash scripts/setup_env.sh" >&2
  exit 2
fi

if ! env -u PYTHONPATH "$PYTHON" -c 'import wg_deck; import PySide6'; then
  echo "Python installation incomplete. Run: bash scripts/setup_env.sh" >&2
  exit 2
fi

exec env -u PYTHONPATH "$PYTHON" -m wg_deck "$@"
