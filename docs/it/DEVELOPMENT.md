# Sviluppo e gate di qualità — Italiano

Test e build ordinarie si eseguono **prima in locale** con Python 3.12, uv e utente desktop non root.

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
bash scripts/capture_demo_suite.sh
```

Il gate controlla sintassi Python e helper, XML delle policy, script shell, regressioni unit/security e Qt offscreen. La suite screenshot produce 28 PNG demo sintetici, tavole comparative, manifest e ZIP in `local/` escluso da Git. Non versionare backup, profili veri, nomi sensibili o log non anonimizzati.

## Test del codice privilegiato

Il contenuto di `privileged/` è una boundary di sicurezza. Ogni modifica richiede test mirati, installazione root-owned esplicita e smoke su un profilo **disconnesso e sacrificabile**. Non testare sulla VPN necessaria per l'accesso remoto. Gli helper non vanno avviati direttamente dal checkout scrivibile.

## Pull request

- Modifiche mirate, motivazione e documentazione aggiornata in entrambe le lingue.
- `local_gate.sh` e QA visuale per interventi UI.
- Evidenziare cambiamenti a permessi, Polkit, systemd e parser.
- Solo log anonimizzati e immagini demo, mai chiavi.
- Verificare wheel/sdist e gli SVG prima di una release.

## Struttura

`src/wg_deck/` — app; `privileged/` — sicurezza; `scripts/` — setup e QA; `tests/` — regressioni; `docs/en/`, `docs/it/` — documentazione pubblica.

Per vulnerabilità consulta [SECURITY.md](../../SECURITY.md).
