#!/usr/bin/env bash
set -euo pipefail
echo "Uninstall helper only. Existing profiles and live VPNs are NOT modified."
sudo systemctl disable --now wg-deck-inventory.timer || true
sudo systemctl disable --now wg-deck-inventory.path || true
sudo systemctl stop wg-deck-inventory.service || true
sudo rm -f /etc/systemd/system/wg-deck-inventory.path /etc/systemd/system/wg-deck-inventory.service /etc/systemd/system/wg-deck-inventory.timer
sudo systemctl daemon-reload
sudo rm -f /run/wg-deck-profiles.list
sudo rm -f /run/wg-deck-traffic.tsv
sudo rm -f /etc/wg-deck-reader-gid
sudo rm -f /usr/local/libexec/wg-deck-inventory
sudo rm -f /usr/local/libexec/wg-deck-read
sudo rm -f /usr/share/polkit-1/actions/org.matt88.wgdeck.read.policy
sudo rm -f /usr/local/libexec/wg-deck-connection
sudo rm -f /usr/share/polkit-1/actions/org.matt88.wgdeck.connection.policy
sudo rm -f /usr/local/libexec/wg-deck-helper
sudo rm -f /usr/share/polkit-1/actions/org.matt88.wgdeck.policy
echo "Helper removed; profiles and running VPN interfaces remain in place."
