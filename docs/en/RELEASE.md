# Build, releases and download analytics — English

## What gets released

The first public release uses a **tagged, reviewed commit** (`v1.0.0`), never an unverified source snapshot. GitHub automatically generates Source code ZIP/TAR archives for the tag. We additionally attach:

- `wg_deck-1.0.0-py3-none-any.whl` — Python distribution (installs Python code/assets but **does not** automatically install root-owned Polkit/systemd helpers).
- `wg_deck-1.0.0.tar.gz` — Python source distribution, including `privileged/`, `scripts/`, EN/IT documentation and the canonical SVGs (validated by `scripts/build_release.sh`).
- `SHA256SUMS` — checksums for uploaded assets.

The `.whl` is a **Python distribution, not a standalone executable**: Linux with Python 3.12, Qt runtime and system tools is still required. An optional `.deb` for Ubuntu x86_64/arm64 is deferred until end-to-end package installation, uninstall, privilege-policy and upgrade tests exist. We do not advertise an AppImage as fully self-contained when privileged helpers still require audited host integration.

## Local-first build

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
.venv/bin/python -m pip --version  # optional; use uv pip for dependency management
uv pip install --python .venv/bin/python build
.venv/bin/python -m build
sha256sum dist/* > dist/SHA256SUMS
```

Review the source distribution and wheel contents; ensure canonical SVGs are packaged. No binaries or archives should contain local `.conf` files, keys, `.env` or private evidence.

## Release workflow

1. Finish privacy/secret scanning on the public snapshot **before** public push.
2. Verify public repository tests and builds, including screenshots on Ubuntu.
3. Validate at least one clean Linux installation and removal with a disposable VPN profile.
4. Obtain owner approval on the **exact release commit SHA**.
5. Create the annotated `v1.0.0` tag on that SHA and publish a GitHub Release with the assets above.
6. Record checksums and publish links on matt88.it only after the GitHub download URLs work.

The repository CI builds packages for inspection. A separate draft-release workflow can be enabled after the initial security gate; no release is published automatically from an unverified feature branch.

## Download counts

GitHub's **release assets API** exposes a `download_count` per uploaded asset. For example, a nightly or monthly report may read `GET /repos/matteodurso88/wg-deck/releases` and total *asset* counts by version and architecture. This is an aggregate counter, **not unique users** or installations. GitHub's automatically generated Source code archives do not provide the same per-uploaded-asset download accounting. To measure ZIP-source downloads too, upload an explicitly named source asset; do not infer them from page views.

To inspect public aggregate counts after a release, run `python3 scripts/release_downloads.py` (or `--json` for machine-readable output). This performs an explicit read-only GitHub API request; WG Deck itself does not collect telemetry.

See https://docs.github.com/en/rest/releases/assets.
