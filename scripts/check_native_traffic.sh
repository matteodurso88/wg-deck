#!/usr/bin/env bash
# Secret-safe, unprivileged verification of periodic WireGuard metrics.
# Only statuses/counts are printed; no public keys, traffic values or config.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail=0
ok() { printf 'PASS  %s\n' "$1"; }
bad() { printf 'FAIL  %s\n' "$1"; fail=$((fail+1)); }

timer=wg-deck-inventory.timer
unit=wg-deck-inventory.service
snapshot=/run/wg-deck-traffic.tsv
publisher=/usr/local/libexec/wg-deck-inventory

if [[ "$(systemctl is-enabled "$timer" 2>/dev/null || true)" == enabled &&
      "$(systemctl is-active "$timer" 2>/dev/null || true)" == active ]]; then
  ok "10-second root telemetry timer enabled and running"
else
  bad "Telemetry timer missing/inactive (reinstall helper)"
fi

if [[ -r "$publisher" ]]; then
  if cmp -s "$publisher" privileged/wgdeck_inventory.py; then
    ok "Root publisher matches the checked-out source"
  else
    bad "Root publisher differs from working branch"
  fi
else
  bad "Installed root publisher missing"
fi

if [[ -f "$snapshot" && ! -L "$snapshot" &&
      "$(stat -c '%u:%a' "$snapshot")" == "0:640" ]]; then
  ok "Root-owned traffic snapshot has restricted 0640 permissions"
else
  bad "Traffic snapshot absent or has unsafe ownership/mode"
fi

if [[ -x .venv/bin/python ]]; then
  if .venv/bin/python - <<'PY'
from wg_deck.core.traffic import read_native_traffic
rows = read_native_traffic()
if rows is None:
    raise SystemExit(1)
# Never print names, amounts, endpoints or peer keys.
print(f"PASS  Fresh secret-free snapshot ({len(rows)} native profile(s) observed)")
PY
  then :; else bad "Traffic snapshot unreadable, malformed or older than 30s"; fi
else
  bad "Python virtual environment missing"
fi
if [[ "$fail" -ne 0 ]]; then
  printf 'TRAFFIC MONITOR GATE FAIL (%s check(s))\n' "$fail"
  exit 1
fi
echo "TRAFFIC MONITOR GATE PASS — does not imply peer handshake or packet transfer."
