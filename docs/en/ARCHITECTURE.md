# Architecture — English

WG Deck is a Python 3.12 / PySide6 desktop application. The GUI is never run as root; external system changes are made through narrowly scoped helper commands and Polkit authorization.

```text
PySide6 UI (src/wg_deck/ui)
    │
    ├── unprivileged core: models, discovery, profile parser, validation
    │   ├── /run/wg-deck-profiles.list (root-owned, names only)
    │   └── /run/wg-deck-traffic.tsv (restricted, no secrets)
    │
    ├── explicit Polkit read / connect / manage actions
    │   └── /usr/local/libexec/wg-deck-*
    │        └── wg-quick and systemd for authorized changes
    │
    └── Qt tray, desktop integration and opt-in XDG autostart

Root-owned systemd inventory .service + .path + .timer
    └── /etc/wireguard/*.conf (names, statistics; never print keys)
```

The system's `/etc/wireguard/` directory remains canonical: WG Deck never maintains a second catalogue of native profiles. Cached Qt settings store UI preferences only.

**Product identifiers:** the Python package is wg_deck; helper executables, Polkit policies and systemd units use wg-deck or org.matt88.wgdeck. Existing pre-release installations must explicitly remove the old helpers before installing this public version; profile files and active tunnels are never modified during repository migration.

See [security model](SECURITY.md) and the source modules in `privileged/` for the precise allowlists and file permissions.
