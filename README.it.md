# WG Deck

**Applicazione desktop Linux per gestire i profili WireGuard nativi.**

WG Deck integra una Dashboard PySide6, editor dei profili, diagnostica in sola lettura e system tray. Utilizza le configurazioni reali `/etc/wireguard/*.conf` mediante helper Polkit separati, installati con autorizzazione esplicita.

> **Stato:** candidata alla v1.0.0. Il codice pubblico non implica che i pacchetti o tutti i gate sulle operazioni privilegiate siano già stati approvati.

## Funzioni

- Individuazione automatica dei profili nativi, senza catalogo separato.
- Stato interfacce, traffico RX/TX e handshake osservati; valori non disponibili non diventano falsi zeri.
- Connessione/disconnessione previa autorizzazione esplicita.
- Creazione, modifica, importazione ed esportazione con controlli di sicurezza.
- Backup ZIP privato dei profili: **contiene chiavi private**.
- Temi Light/Dark/System, tray e autoavvio opzionale della sola GUI.
- Modalità demo con dati completamente sintetici.

## Installazione — pacchetto Debian (Ubuntu 26.04)

La distribuzione ufficiale prevista è un solo **.deb**, con Python e PySide6 gestiti da APT anziché inclusi nel pacchetto. Quando la release sarà approvata, potrai installarlo con:

```bash
sudo apt install ./wg-deck_1.0.0-2_all.deb
wg-deck --demo
```

Il pacchetto installa app, icone, helper root-owned, policy Polkit e unità systemd. Su Ubuntu **attiva automaticamente il publisher in sola lettura**: i profili WireGuard esistenti sono disponibili già al primo avvio, senza comandi aggiuntivi. **Non connette né disconnette VPN.** Nella modalità predefinita i metadati sanitizzati sono leggibili dagli utenti locali; un amministratore può limitarli a un gruppo primario usando `sudo wg-deck-setup --restrict-inventory "$USER"`. Per rimozione e upgrade consulta [Installazione](docs/it/INSTALL.md). La v1.0.0 è ancora candidata, **non una release già pubblicata**.

## Anteprima dai sorgenti

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

Lo sviluppo usa Python 3.12 e uv. Non combinare gli helper manuali di `scripts/install_helper.sh` con quelli di APT.

## Documentazione

[Installazione](docs/it/INSTALL.md) · [Guida utente](docs/it/USAGE.md) · [Sicurezza](docs/it/SECURITY.md) · [Architettura](docs/it/ARCHITECTURE.md) · [Sviluppo](docs/it/DEVELOPMENT.md) · [Build e release](docs/it/RELEASE.md).

Per aggiornare una precedente installazione privata, leggi [la guida](docs/it/UPGRADE.md).

Sono disponibili anche [documentazione inglese](README.md), [contributi](CONTRIBUTING.md), [segnalazioni di sicurezza](SECURITY.md), [changelog](CHANGELOG.md) e [note su marchi e dipendenze](NOTICE.md).

## Indipendenza e licenza

WG Deck è un progetto indipendente, non affiliato né approvato dal progetto WireGuard. Non utilizza il logo ufficiale WireGuard.

Copyright © 2026 Matteo D’Urso. Codice, documentazione originale e asset originali sono distribuiti sotto [GPL-3.0-or-later](LICENSE). Le licenze delle dipendenze restano invariate.
