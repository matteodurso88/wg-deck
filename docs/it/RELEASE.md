# Build, release e statistiche download — Italiano

## Artefatti della release

La prima release pubblica deriva da un **commit verificato e taggato** (`v1.0.0`), non da uno snapshot non testato. GitHub genera automaticamente Source code ZIP/TAR per il tag. In aggiunta carichiamo:

- `wg_deck-1.0.0-py3-none-any.whl` — distribuzione Python (non installa automaticamente helper Polkit/systemd root-owned).
- `wg_deck-1.0.0.tar.gz` — sorgenti completi, compresi `privileged/`, `scripts/`, guide EN/IT e SVG canonici (controllati da `scripts/build_release.sh`).
- `SHA256SUMS` — checksum degli asset.

La `.whl` **non è un eseguibile standalone**: servono Python 3.12, runtime Qt e strumenti di sistema. Rimandiamo un eventuale `.deb` Ubuntu x86_64/arm64 fino a test completi di installazione/rimozione, policy privilegi, aggiornamenti e rollback. Una AppImage non sarebbe completamente autonoma per gli helper privilegiati.

## Build Local-First

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
uv pip install --python .venv/bin/python build
.venv/bin/python -m build
sha256sum dist/* > dist/SHA256SUMS
```

Ispeziona contenuto della wheel e del sdist: tutti gli SVG devono essere presenti, senza `.conf` reali, chiavi, `.env` o dati privati.

## Procedura di pubblicazione

1. Scansionare e revisionare lo snapshot **prima** del push pubblico.
2. Testare la build nel nuovo repository e acquisire screenshot demo.
3. Collaudare installazione e rimozione su Linux pulito con profilo di laboratorio.
4. Ottenere approvazione dell'owner sullo **SHA esatto**.
5. Creare tag annotato `v1.0.0` e GitHub Release con artefatti e checksum.
6. Pubblicare link su matt88.it soltanto quando gli URL di download risultano verificati.

La CI crea build da ispezionare; il workflow release in bozza può essere abilitato dopo il gate di sicurezza. Non pubblicare automaticamente da un branch non collaudato.

## Tracciatura download

La GitHub Release Assets API espone `download_count` per ogni asset caricato: permette riepiloghi aggregati per versione/architettura. **Non indica utenti unici né installazioni.** Gli archivi Source code auto-generati non offrono lo stesso contatore per asset caricati; per tracciarne i download bisogna allegare un archivio sorgente nominato esplicitamente, senza confondere i numeri con le visite alla pagina.

Dopo la prima release puoi leggere i contatori pubblici con `python3 scripts/release_downloads.py` oppure `--json`: interroga la GitHub API solo su richiesta. WG Deck non inserisce tracking o telemetria utenti nell'applicazione.

Documentazione: https://docs.github.com/en/rest/releases/assets.
