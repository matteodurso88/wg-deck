# WG Deck — Debian-only releases

The only uploaded runtime artifact is **wg-deck_1.0.0-2_all.deb**, accompanied by **SHA256SUMS**. GitHub automatically generates Source code ZIP/TAR archives for the tag. No wheel, pip sdist or AppImage is uploaded.

## Compatibility
Initial target: **Ubuntu 26.04 LTS** with the distribution's Python 3.12+, PySide6 6.10+, Qt, systemd, Polkit and WireGuard utilities. The package contains pure Python and is named `_all.deb`; this does not mean it supports every distribution. Ubuntu 24.04 has no equivalent distro PySide6 packages and is not a supported target. AMD64 and ARM64 must each pass a clean-host test.

## Local-first build and test
```bash
bash scripts/setup_env.sh
bash scripts/build_release.sh
```

Outputs:
```text
dist/wg-deck_1.0.0-2_all.deb
dist/SHA256SUMS
```

A packaging-only iteration may use `bash packaging/debian/build.sh` and `bash packaging/debian/test_deb.sh`. Neither installs system files or touches VPNs. The package includes the desktop launcher, original SVGs, root-owned helpers, Polkit actions, systemd publisher units and bilingual manuals.

## Installation contract
APT manages Python/PySide6. Installing and upgrading automatically enables the **read-only** inventory publisher on systemd hosts, making existing profile names and non-secret traffic metadata available at first launch. It does not connect a VPN, alter routes or change existing configurations under `/etc/wireguard`. Snapshots are root-owned but readable by local users (`0644`) by default; optionally restrict to a primary group (`0640`) using `sudo wg-deck-setup --restrict-inventory "$USER"`. It can be disabled with `sudo wg-deck-setup --disable-inventory`. Removal stops only the WG Deck publisher; purge also deletes its own reader-group setting and generated snapshots. Do not combine APT and manual development helper installations.

## Release gate
1. Local tests and security scan green, CI including Ubuntu 26.04 container install/remove green.
2. Real GNOME/Wayland and Polkit smoke, upgrade, rollback and safe removal on a disposable profile. Never disconnect a remote-access tunnel.
3. Review exact SHA, permissions, dependencies and third-party license obligations.
4. Obtain owner approval, create the annotated tag `v1.0.0`, manually trigger `Draft tagged release`.
5. Review the draft with only `.deb` and `SHA256SUMS`; publish manually after explicit approval and verify links.

**A green build is not a published release.**

## Download metrics
GitHub's Release Assets API exposes an aggregate `download_count` per uploaded .deb, not unique users or installations. Automatically generated source ZIP/TAR do not have this uploaded-asset counter. Use `python3 scripts/release_downloads.py --json`. No in-app tracking is implemented.
