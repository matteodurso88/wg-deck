# WG Deck

**A native Linux desktop application for managing WireGuard profiles.**

WG Deck combines a PySide6 dashboard, a profile editor, read-only diagnostics and a system-tray interface. It works with native `/etc/wireguard/*.conf` configurations through narrowly scoped, separately authorized Polkit helpers.

> **Release status:** v1.0.0 candidate. This public source snapshot is not a claim that binary packages or privileged operations have passed the final distribution checks.

## Features

- Discover native WireGuard profiles without maintaining a separate profile registry.
- View interface state, RX/TX counters and observed handshakes; unavailable measurements are not presented as zero.
- Connect/disconnect profiles after explicit authorization.
- Create, review, edit, import and export supported configurations with safeguards.
- Back up native profiles to a private ZIP; **archives contain private keys**.
- Choose Light, Dark or System theme, optional tray and opt-in GUI autostart.
- Preview the application safely with synthetic demo data.

## Installation — Debian package (Ubuntu 26.04)

The planned official distribution is a single **.deb**, with Python and PySide6 supplied by Ubuntu APT rather than bundled. Once an approved release exists, the package can be installed with:

```bash
sudo apt install ./wg-deck_1.0.0-2_all.deb
wg-deck --demo
```

The package installs the app, icons, root-owned helpers, Polkit policies and systemd units. On a normal Ubuntu system it **automatically starts the read-only inventory publisher**, so existing WireGuard profiles are visible at first launch without a setup command. It **never starts or stops a VPN**. The sanitized name and traffic snapshots are readable by local users by default; an administrator can restrict access to one primary group with `sudo wg-deck-setup --restrict-inventory "$USER"`. For removal and upgrades see [Installation](docs/en/INSTALL.md). The .deb for v1.0.0 is still a release candidate, **not yet published**.

## Source/developer preview

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

Source development uses Python 3.12 and uv. Do not mix manually installed `scripts/install_helper.sh` helpers with the APT-owned Debian package.

## Documentation

| English | Italiano |
|---|---|
| [Installation](docs/en/INSTALL.md) | [Installazione](docs/it/INSTALL.md) |
| [User guide](docs/en/USAGE.md) | [Guida utente](docs/it/USAGE.md) |
| [Security](docs/en/SECURITY.md) | [Sicurezza](docs/it/SECURITY.md) |
| [Architecture](docs/en/ARCHITECTURE.md) | [Architettura](docs/it/ARCHITECTURE.md) |
| [Development & tests](docs/en/DEVELOPMENT.md) | [Sviluppo e test](docs/it/DEVELOPMENT.md) |
| [Build & release](docs/en/RELEASE.md) | [Build e release](docs/it/RELEASE.md) |

For earlier private installations, read [the upgrade guide](docs/en/UPGRADE.md).

See also [Italian README](README.it.md), [contributing](CONTRIBUTING.md), [security disclosure](SECURITY.md), [changelog](CHANGELOG.md) and [branding and third-party notices](NOTICE.md).

## Project independence

WG Deck is **not** developed, approved, sponsored or maintained by the WireGuard project. WireGuard® and its logo are marks of their respective owner. WG Deck uses its own original application identity and does not reproduce the WireGuard logo.

## License

Copyright © 2026 Matteo D’Urso. Source code, original documentation and bundled original artwork are provided under [GPL-3.0-or-later](LICENSE). The GPL grants copyright permissions but does not grant rights to represent another organization or claim trademark endorsement. Third-party dependencies keep their own licenses; see [NOTICE.md](NOTICE.md).
