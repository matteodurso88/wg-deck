# Security model — English

WG Deck's Qt GUI is deliberately **unprivileged**. Authorization and system mutations occur only in preinstalled, root-owned, allowlisted helpers. Treat every WireGuard configuration as sensitive data and as potentially executable input through `wg-quick` hooks.

## Privilege separation

- **Read** (separate Polkit action): read/export protected configurations; the session may have a short authorization cache controlled by Polkit.
- **Connection** (separate action): `up/down` after relevant checks and optional UI confirmation; a short Polkit cache may apply.
- **Manage**: create, replace, import ZIP and delete with a fresh `auth_admin` request for each operation.
- **Inventory publisher**: root-owned systemd path/service/timer publishes only native names and secret-free, bounded RX/TX/handshake information to restricted `/run` snapshots; no private keys.

## Defense in depth

Native profile names are validated. Writes reject unsafe symlinks and name collisions, respect restrictive `0600` file modes, and use revision checks, protected backups and atomic replacement where applicable. Unsupported directives and hooks are not silently rewritten. GUI autostart is unprivileged and never connects a VPN by itself. No private keys belong in logs, screenshots, Git history or issues.

## Debian packaging and explicit privileges

The Debian package installs executable helpers as root-owned files in `/usr/lib/wg-deck/` and Polkit policies in `/usr/share/polkit-1/actions/`. Installation automatically activates the **read-only** inventory publisher on systemd hosts, but never starts/stops VPN interfaces. Its root-owned, sanitized profile-name and traffic snapshots are world-readable (`0644`) by default, so other local users can see these metadata, including interface names and transfer counters. The snapshots never include keys, endpoints or configuration contents. On shared machines, restrict access to the selected user's primary group (`0640`) with `sudo wg-deck-setup --restrict-inventory USER`. This restriction is optional and no manual setup is needed for first launch. APT removal and purge do not touch `/etc/wireguard/`. Do not mix manual developer helpers installed under `/usr/local/libexec` with the APT-managed package.

## Residual risks

- A **trusted existing** `.conf` may contain `PreUp`, `PostUp`, `PreDown`, `PostDown`; `wg-quick` executes these with elevated privileges. Do not connect unknown/untrusted profiles.
- Reading/exporting configs intentionally exposes keys to the authenticated user; exported ZIPs must remain private and restricted.
- An interface can be UP without any handshake; counters and reachability are not interchangeable.
- An installer must be inspected before granting `sudo` privileges. Qt demo tests alone are not security acceptance.
- Shell integration, Qt plugins and packaged system libraries require separate security and license QA before binary releases.

Report vulnerabilities privately using [SECURITY.md](../../SECURITY.md) rather than public issues.
