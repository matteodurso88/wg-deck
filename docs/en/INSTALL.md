# Installation — Ubuntu 26.04 LTS

The official distribution candidate is a **Debian package**, currently undergoing the release gate. Ubuntu 26.04 is the initial validated APT dependency target; other distributions require separate testing. The package relies on the system Python 3.12+ and PySide6 6.10+ packages from Ubuntu's `universe` repository. Do not run the graphical app as root.

## Install a locally verified candidate

Only install a package downloaded from a trusted, reviewed GitHub Release or built by you from this repository. Until `v1.0.0` is published, this command refers to a **local build candidate**, not a public release.

```bash
cd ~/progetti/wg-deck
bash scripts/setup_env.sh
bash scripts/build_release.sh
sudo apt install ./dist/wg-deck_1.0.0-2_all.deb
wg-deck --demo
```

APT installs the application into `/usr/lib/python3/dist-packages/wg_deck`, executable `/usr/bin/wg-deck`, helper files into `/usr/lib/wg-deck`, systemd inventory units and Polkit policies. The launcher appears in your application menu. Qt and Python dependencies are installed and updated by APT. **Installation enables the read-only inventory path/timer automatically and publishes existing profile names immediately. It does not connect/disconnect tunnels or change routes.**

## Inventory works automatically; optional privacy restriction

No setup command is needed after installing on a normal systemd Ubuntu desktop. The root-owned publisher immediately creates sanitized profile-name and traffic snapshots (`0644`), readable by all local users. **This includes connection metadata, but never private keys, endpoints or configuration contents.** On a multi-user computer, an administrator may restrict snapshot visibility to the selected account's primary group (`0640`) with:

```bash
sudo wg-deck-setup --restrict-inventory "$USER"
systemctl status wg-deck-inventory.timer
```

This restricts the snapshot reader group and refreshes WG Deck's already running read-only inventory publisher. It does not run `wg-quick up` or `wg-quick down`. To stop the publisher:

```bash
sudo wg-deck-setup --disable-inventory
```

Polkit permission is still required for reading secret configuration contents and for any native profile change. Existing WireGuard configurations remain owned by the system, not by the package.

## Remove or update

Turn off **Start on login** in the UI before uninstalling. Use `sudo apt remove wg-deck` to remove the package and stop its own inventory publisher. `sudo apt purge wg-deck` also removes the tool's generated state and reader-group setting. **Neither command deletes `/etc/wireguard` or stops an active VPN.** Upgrades are managed by normal APT package replacement; smoke test with a disposable profile.

## Development installation (separate workflow)

If you prefer a source checkout for development, run:

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

The manual `scripts/install_helper.sh` workflow is for source-development installations only. Do not run it while the APT-managed package is installed; avoid duplicate Polkit action IDs and systemd units. For historical private installs see [Upgrade](UPGRADE.md).

Never disconnect a tunnel used by your remote session. Test privileged operations on a disposable local profile only.
