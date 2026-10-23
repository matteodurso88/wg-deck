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

## Avvio rapido

Per la GUI servono Linux, Python **3.12** e [uv](https://docs.astral.sh/uv/). Per le funzioni native complete: `wireguard-tools`, `iproute2`, systemd e Polkit.

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

Prima di installare gli helper privilegiati con `bash scripts/install_helper.sh`, leggere la [guida all'installazione](docs/it/INSTALL.md): lo script richiede `sudo`, crea file di sistema root-owned e non avvia automaticamente i tunnel.

## Documentazione

[Installazione](docs/it/INSTALL.md) · [Guida utente](docs/it/USAGE.md) · [Sicurezza](docs/it/SECURITY.md) · [Architettura](docs/it/ARCHITECTURE.md) · [Sviluppo](docs/it/DEVELOPMENT.md) · [Build e release](docs/it/RELEASE.md).

Per aggiornare una precedente installazione privata, leggi [la guida](docs/it/UPGRADE.md).

Sono disponibili anche [documentazione inglese](README.md), [contributi](CONTRIBUTING.md), [segnalazioni di sicurezza](SECURITY.md), [changelog](CHANGELOG.md) e [note su marchi e dipendenze](NOTICE.md).

## Indipendenza e licenza

WG Deck è un progetto indipendente, non affiliato né approvato dal progetto WireGuard. Non utilizza il logo ufficiale WireGuard.

Copyright © 2026 Matteo D’Urso. Codice, documentazione originale e asset originali sono distribuiti sotto [GPL-3.0-or-later](LICENSE). Le licenze delle dipendenze restano invariate.
