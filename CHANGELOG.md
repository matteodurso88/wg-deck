# Changelog

This project follows [Semantic Versioning](https://semver.org/) for releases.

## [Unreleased]

- Public repository extraction from the private WORKSHOP development project.
- Initial bilingual public documentation, security and release policies.
- Debian-only distribution candidate for Ubuntu 26.04 with APT-managed Python/PySide6, safe Polkit/systemd helper packaging, opt-in inventory setup, checksum verification and disposable installation/removal QA. No wheel/sdist release assets.
- GitHub Actions Qt host dependency repair (`libEGL.so.1`) and package install/reinstall/remove/purge safeguards.

## [1.0.0] — planned, not released

- Native WireGuard profile dashboard, safe editor and read-only diagnostics.
- Separate Polkit authorization scopes for read, connection and administration.
- Protected single-profile and ZIP backup export/import.
- Observed RX/TX and handshake telemetry via a restricted systemd publisher.
- Light/Dark/System appearance and optional user-session autostart.
- WG Deck original Concept 09 identity and demo screenshot tooling.

**Do not turn the planned heading into a released version until the v1.0.0 GitHub Release and its exact commit have been validated.**
