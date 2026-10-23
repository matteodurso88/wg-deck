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

## Getting started

Linux, Python **3.12**, [uv](https://docs.astral.sh/uv/), `wireguard-tools`, `iproute2`, systemd, and Polkit are required for the full installation. The desktop UI may be tested without administrative access.

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

For **privileged native profile management**, review [the English installation guide](docs/en/INSTALL.md) *before* running `bash scripts/install_helper.sh`. This script explicitly requests administrative privileges and installs root-owned helpers and systemd units. It does not activate a VPN automatically.

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
