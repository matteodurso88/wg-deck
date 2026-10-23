#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as desktop user. sudo will be requested for installing trusted files." >&2
  exit 2
fi
command -v pkexec >/dev/null || { echo "Install policykit-1 and a graphical Polkit agent." >&2; exit 2; }
command -v wg-quick >/dev/null || { echo "Install wireguard-tools." >&2; exit 2; }
command -v ip >/dev/null || { echo "Install iproute2." >&2; exit 2; }
sudo install -d -o root -g root -m 0755 /usr/local/libexec
sudo install -o root -g root -m 0755 privileged/wgdeck_helper.py /usr/local/libexec/wg-deck-helper
sudo install -o root -g root -m 0644 privileged/org.matt88.wgdeck.policy /usr/share/polkit-1/actions/org.matt88.wgdeck.policy
# A separate restricted auth_admin_keep action is used ONLY for up/down.
sudo install -o root -g root -m 0755 privileged/wgdeck_connection.py /usr/local/libexec/wg-deck-connection
sudo install -o root -g root -m 0644 privileged/org.matt88.wgdeck.connection.policy /usr/share/polkit-1/actions/org.matt88.wgdeck.connection.policy
# Separate secret-reading token may be reused briefly; config mutation remains auth_admin.
sudo install -o root -g root -m 0755 privileged/wgdeck_read.py /usr/local/libexec/wg-deck-read
sudo install -o root -g root -m 0644 privileged/org.matt88.wgdeck.read.policy /usr/share/polkit-1/actions/org.matt88.wgdeck.read.policy
# Root-owned read-only profile index; never contains .conf contents or keys.
# Preserve existing /etc/wireguard directory permissions and ACLs.
if [[ ! -d /etc/wireguard ]]; then
  sudo install -d -o root -g root -m 0700 /etc/wireguard
fi
# Limit the names-only snapshot to the desktop user's primary group.
sudo install -o root -g root -m 0600 /dev/null /etc/wg-deck-reader-gid
printf '%s\n' "$(id -g)" | sudo tee /etc/wg-deck-reader-gid >/dev/null
sudo install -o root -g root -m 0755 privileged/wgdeck_inventory.py /usr/local/libexec/wg-deck-inventory
sudo install -o root -g root -m 0644 privileged/wg-deck-inventory.service /etc/systemd/system/wg-deck-inventory.service
sudo install -o root -g root -m 0644 privileged/wg-deck-inventory.path /etc/systemd/system/wg-deck-inventory.path
sudo install -o root -g root -m 0644 privileged/wg-deck-inventory.timer /etc/systemd/system/wg-deck-inventory.timer
sudo systemctl daemon-reload
# /run is volatile: publish at every boot, not only on a later directory change.
sudo systemctl enable wg-deck-inventory.service
sudo systemctl enable --now wg-deck-inventory.path
sudo systemctl enable --now wg-deck-inventory.timer
sudo systemctl start wg-deck-inventory.service
echo "Trusted root-owned helper installed. Restart the GUI."
echo "All native /etc/wireguard profiles share the same Polkit operations."
echo "Names-only inventory + secret-free RX/TX snapshots update automatically (10s timer). No traffic Polkit prompts."
echo "Connections and read/export use distinct short-lived Polkit grants; install/replace/delete stay per-action."
