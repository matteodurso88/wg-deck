# Upgrade from the private development installation

WG Deck v1.0.0 has clean public technical identifiers. The previous private development build installed services, desktop entries and Polkit actions under an earlier name. **Do not delete /etc/wireguard or disconnect an active tunnel as part of this transition.**

1. Close the old WG Deck GUI completely, including its system tray. If the old GUI has **Start on login** enabled, turn it off first; verify it is disabled.
2. In the **previous private WORKSHOP checkout**, review and run `bash scripts/uninstall_desktop.sh` as your normal desktop user. It removes the owned old desktop integration only.
3. From that same old checkout, inspect `scripts/uninstall_helper.sh` before explicitly running it. It disables the old inventory publisher and removes only the prior application's helper/policy/unit files. It **does not** remove WireGuard profiles, change routes, or disconnect existing tunnels.
4. From the **new** `~/progetti/wg-deck` checkout, build and inspect the APT-managed `.deb` and install it using `sudo apt install ./dist/wg-deck_1.0.0_all.deb` (Ubuntu 26.04 only). Do **not** mix `scripts/install_helper.sh` with the Debian installation. The package does not automatically enable inventory or connect a VPN. After review, enable read-only inventory explicitly with `sudo wg-deck-setup --enable-inventory "$USER"`.
5. Verify one disposable profile using the native smoke scripts and verify the GNOME tray. Leave a VPN used for remote access untouched.

**Never run old and new inventory publishers in parallel.** Preserve the original WORKSHOP branch until all migration gates are confirmed. The repository renaming script does not modify the system or migrate root-owned files automatically.
