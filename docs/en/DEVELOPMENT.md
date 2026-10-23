# Development and quality gates — English

All ordinary tests and builds run **locally first**. Use Python 3.12, uv and a normal (non-root) desktop user.

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
bash scripts/capture_demo_suite.sh
```

The local gate checks Python syntax, helper syntax, policy XML, shell scripts, unit/security tests and Qt offscreen UI regressions. The screenshot suite exports 28 synthetic demo PNGs, comparison sheets and a manifest/ZIP to the ignored `local/` directory. Do not commit ZIP backups, real profile files, device names or sensitive logs.

## Testing privileged code

Code in `privileged/` is a security boundary. Changes require focused unit tests, a root-owned installation via the explicit installer and an independent smoke on a **disconnected, disposable** local lab profile. Never test on a VPN needed to maintain remote access. Root helper files must not be executed directly from the writable checkout.

## Pull request checks

- Keep change scope small, document behavior and update both language sets.
- Run `local_gate.sh` and visual QA when applicable.
- Mention changes to permissions, Polkit actions, systemd and configuration parser behavior.
- Include only sanitized logs and demo screenshots. Never post real VPN keys.
- Validate Python wheel/sdist packaging and SVG inclusion before release.

## Layout

`src/wg_deck/` — application; `privileged/` — helper/security boundary; `scripts/` — setup, QA and installation; `tests/` — regressions; `docs/en/` and `docs/it/` — maintained public documentation.

For security reporting see [SECURITY.md](../../SECURITY.md).
