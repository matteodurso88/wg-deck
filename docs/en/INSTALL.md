# Installation — English

**Target:** Linux desktop with Python 3.12, systemd, Polkit and WireGuard tools. GNOME/Ubuntu are tested first; other environments require independent verification.

## Requirements

Install Python 3.12, [uv](https://docs.astral.sh/uv/), `wireguard-tools` (`wg`, `wg-quick`), `iproute2`, Polkit (`pkexec` with a desktop authentication agent), and systemd. A graphical tray may additionally need StatusNotifier/AppIndicator support. Do not run the graphical app with `sudo`.

## Demo first — unprivileged

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

The demo uses fictitious data and does not require a VPN configuration.

## Enable native profile management

Review `privileged/` and the [security guide](SECURITY.md). The installer below explicitly uses `sudo` to copy root-owned helpers and Polkit policies and enable an inventory publisher. It creates `/etc/wireguard` **only if absent**; it does not edit existing profiles, open/close tunnels or change routes:

```bash
bash scripts/install_helper.sh
bash scripts/check_native_inventory.sh
bash scripts/check_native_traffic.sh
bash scripts/run.sh
```

After installation, the GUI can read a restricted snapshot of native profile **names** and safe RX/TX counters; reading configuration contents or performing actions still requires Polkit as applicable. Exported `.conf` files and ZIPs contain private keys: use private destinations only.

## Desktop icon and optional autostart

```bash
bash scripts/install_desktop.sh
```

The UI's **Settings → Start on login** toggle enables a user-local XDG autostart desktop entry. It starts **only the GUI**, never a VPN. If you move the checkout, turn the toggle off and back on to update its Exec path. A new public repository folder does not automatically update an older startup entry.

## Uninstallation / upgrades

```bash
bash scripts/uninstall_desktop.sh
```

Before removing privileged helpers, review the exact effects of `scripts/uninstall_helper.sh`. Native WireGuard configurations are user-managed system assets: never delete them as part of an application uninstall. After updates to privileged source files, re-run local gates **before** choosing to reinstall the helpers.

Do not disconnect a tunnel your current remote session relies on. Run destructive profile tests only on an isolated disposable test profile.
