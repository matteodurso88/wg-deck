# User guide — English

## Dashboard

The Dashboard lists native profiles and shows interface state, total traffic, last handshake and per-profile actions. **Interface UP is not proof of a reachable peer**; examine last handshake and RX/TX. If measurements are inaccessible or stale, WG Deck reports unavailable rather than inventing zero traffic.

## Profiles

- **New Profile:** create a valid native `/etc/wireguard/<name>.conf` through explicit Polkit authorization; creation does **not** connect it.
- **Edit:** edit the supported fields; advanced or executable-hook configurations remain preview-only to avoid loss of information. Stop the interface first.
- **Connect/Disconnect:** optionally ask for GUI confirmation and always rely on Polkit; `wg-quick` may change routes/DNS and execute hooks from existing trusted profiles.
- **Export:** write a fresh, non-overwriting `.conf` with mode `0600`.
- **Export All:** package all native configurations, including keys, into a protected ZIP. **Never publish or attach it to an issue.**
- **Import Backup:** accept only validated, missing names; archives with unsupported directives or unsafe hooks must be handled manually by an administrator. Import never automatically starts a VPN.
- **Delete:** permitted only for disconnected profiles under the helper's safeguards and with a root-only backup.

## Settings

Themes: Light, Dark and System. Tray availability depends on the desktop environment. **Start on login** launches only the application. Networking behavior switches that have not passed their gate remain disabled.

## Safe troubleshooting

Use `bash scripts/check_native_inventory.sh` and `bash scripts/check_native_traffic.sh` for restricted diagnostics. Do not post original `.conf` files, `wg showconf` output or raw backup archives. To capture the UI use synthetic `bash scripts/capture_demo_suite.sh`.
