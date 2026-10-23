# Guida utente — Italiano

## Dashboard

La Dashboard mostra profili nativi, stato delle interfacce, traffico, handshake e azioni. **Interfaccia UP non equivale a peer raggiungibile**: controlla handshake e RX/TX. Se i dati non sono accessibili o sono scaduti, WG Deck indica non disponibili, senza falsi zeri.

## Profiles

- **New Profile:** crea `/etc/wireguard/<nome>.conf` con Polkit; non avvia il tunnel.
- **Edit:** modifica solo i campi supportati; i profili complessi o con hook eseguibili restano in anteprima per evitare perdite di informazioni. Prima disconnetti l'interfaccia.
- **Connect/Disconnect:** conferma UI facoltativa, autorizzazione Polkit sempre necessaria; `wg-quick` può cambiare route/DNS o eseguire hook già presenti.
- **Export:** salva un nuovo `.conf` con permessi `0600`, senza sovrascrivere file.
- **Export All:** genera uno ZIP protetto con tutte le configurazioni, **chiavi comprese**. Non pubblicarlo e non allegarlo a issue.
- **Import Backup:** installa soltanto nomi assenti e configurazioni validate; direttive avanzate e hook potenzialmente eseguibili richiedono gestione manuale amministrativa. L'importazione non connette.
- **Delete:** solo profili disconnessi, con verifiche dell'helper e backup protetto root-only.

## Settings

Temi Light/Dark/System. La tray dipende dal desktop. **Start on login** avvia solo l'app. I toggle di networking non ancora collaudati restano disabilitati.

## Diagnostica sicura

Usa `bash scripts/check_native_inventory.sh` e `bash scripts/check_native_traffic.sh`, che non stampano chiavi. Non inviare file `.conf`, output `wg showconf` o ZIP di backup. Per screenshot usa la demo sintetica: `bash scripts/capture_demo_suite.sh`.
