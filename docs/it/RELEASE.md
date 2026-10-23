# WG Deck — distribuzione esclusivamente Debian

Per ogni versione approvata vengono caricati **wg-deck_1.0.0-2_all.deb** e **SHA256SUMS**. GitHub crea automaticamente gli archivi Source code ZIP/TAR associati al tag. Non sono previsti wheel, sdist pip o AppImage come artefatti pubblici.

## Compatibilità
Primo target: **Ubuntu 26.04 LTS** con Python 3.12+, PySide6 6.10+, Qt, systemd, Polkit e strumenti WireGuard gestiti da APT. Il suffisso `_all.deb` indica codice Python indipendente dall'architettura, non compatibilità universale. Ubuntu 24.04 non offre gli stessi pacchetti PySide6 nativi ed è escluso per il momento. AMD64 e ARM64 richiedono collaudi separati.

## Build e verifica Local-First
```bash
bash scripts/setup_env.sh
bash scripts/build_release.sh
```

Output:
```text
dist/wg-deck_1.0.0-2_all.deb
dist/SHA256SUMS
```

Per iterazioni limitate al pacchetto usa `bash packaging/debian/build.sh` e `bash packaging/debian/test_deb.sh`. Non installano nulla sull'host né operano sulle VPN. Il pacchetto include launcher, SVG originali, helper root-owned, policy Polkit, unità systemd e documenti bilingui.

## Contratto d'installazione
Python/PySide6 sono gestiti da APT. Installazione e aggiornamento abilitano automaticamente il publisher **in sola lettura** sui sistemi systemd, rendendo subito visibili i nomi dei profili già esistenti e i metadati di traffico senza chiavi. Non connettono VPN, non modificano route o configurazioni in `/etc/wireguard`. Gli snapshot root-owned sono leggibili dagli utenti locali (`0644`), oppure limitabili al gruppo primario (`0640`) tramite `sudo wg-deck-setup --enable-inventory "$USER"` e disattivato con `sudo wg-deck-setup --disable-inventory`. La rimozione arresta soltanto il publisher WG Deck; il purge elimina anche gruppo lettore e snapshot generati. Evita di combinare gli helper installati manualmente con quelli gestiti da APT.

## Gate di pubblicazione
1. Test e scansione segreti locali verdi, CI verde incluso install/remove isolato Ubuntu 26.04.
2. Smoke GNOME/Wayland e Polkit reali, upgrade, rollback e disinstallazione con profilo sacrificabile. Non scollegare VPN utilizzate per accesso remoto.
3. Revisione SHA esatto, permessi, dipendenze e licenze delle librerie.
4. Approvazione del proprietario, tag annotato `v1.0.0` e avvio manuale di `Draft tagged release`.
5. Verifica della bozza con soli `.deb` e `SHA256SUMS`, poi pubblicazione manuale e controllo dei link.

**Build verde non significa release pubblicata.**

## Download
La GitHub Release Assets API espone `download_count` aggregato per il pacchetto .deb: non indica utenti unici o installazioni. Gli archivi sorgenti automatici non hanno lo stesso contatore. Consulta `python3 scripts/release_downloads.py --json`. Nessuna telemetria nell'app.
