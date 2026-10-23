#!/usr/bin/env bash
# Read-only Dell native profile inventory verification.
# No sudo, no wg-quick, no config contents or profile names printed.
set -u
cd "$(dirname "$0")/.."

failures=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

helper=/usr/local/libexec/wg-deck-helper
source_helper=privileged/wgdeck_helper.py
inventory=/run/wg-deck-profiles.list
service=wg-deck-inventory.service
watcher=wg-deck-inventory.path

if command -v systemctl >/dev/null 2>&1; then
  if [[ "$(systemctl is-enabled "$watcher" 2>/dev/null)" == "enabled" ]] &&
     [[ "$(systemctl is-active "$watcher" 2>/dev/null)" == "active" ]]; then
    pass "Systemd directory watcher enabled and active"
  else
    fail "Systemd directory watcher missing/inactive"
  fi
  if [[ "$(systemctl is-enabled "$service" 2>/dev/null)" == "enabled" ]]; then
    pass "Names-only publisher enabled for cold boots"
  else
    fail "Publisher not enabled for cold boots (update installer)"
  fi
else
  fail "systemctl unavailable"
fi

if [[ -f "$helper" && -r "$helper" && -f "$source_helper" ]]; then
  actual=$(sha256sum "$helper" | cut -d' ' -f1)
  expected=$(sha256sum "$source_helper" | cut -d' ' -f1)
  if [[ "$actual" == "$expected" ]]; then
    pass "Installed root helper matches checked-out branch"
  else
    fail "Installed root helper differs from checked-out source"
  fi
else
  fail "Trusted helper absent or not readable"
fi

if [[ -f "$inventory" && ! -L "$inventory" ]]; then
  owner=$(stat -c '%u' "$inventory")
  group=$(stat -c '%g' "$inventory")
  mode=$(stat -c '%a' "$inventory")
  if [[ "$owner" == "0" && "$mode" == "640" ]] && [[ " $(id -G) " == *" $group "* ]]; then
    pass "Root-owned names-only snapshot 0640 readable by current user group"
  else
    fail "Native snapshot ownership, mode or reader group invalid"
  fi
else
  fail "Native names-only snapshot unavailable"
fi

if [[ -x .venv/bin/python ]]; then
  if .venv/bin/python - <<'PY'
from wg_deck.core.system_profiles import read_native_names
names = read_native_names()
if names is None:
    raise SystemExit(1)
print(f"PASS  Native system inventory readable ({len(names)} profile name(s); names redacted)")
PY
  then :; else fail "Native inventory Python reader rejected the snapshot"; fi
else
  fail "Python environment missing"
fi

printf '\n'
if [[ "$failures" -eq 0 ]]; then
  echo "NATIVE INVENTORY GATE PASS — does not confirm tunnel connectivity."
else
  printf 'NATIVE INVENTORY GATE FAIL — %s check(s) need attention.\n' "$failures"
fi
exit "$((failures > 0))"
