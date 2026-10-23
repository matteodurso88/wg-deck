# Installazione — Ubuntu 26.04 LTS

La distribuzione ufficiale candidata è un **pacchetto Debian**, ancora soggetto al gate di release. Ubuntu 26.04 è il primo target per le dipendenze APT; le altre distribuzioni richiedono collaudi separati. Il pacchetto usa Python di sistema 3.12+ e PySide6 6.10+ dai repository Ubuntu `universe`. Non eseguire mai la GUI come root.

## Installazione del candidato locale verificato

Installa soltanto file provenienti da una GitHub Release approvata o generati da te dai sorgenti revisionati. Fino alla pubblicazione di `v1.0.0`, questo comando riguarda un **candidato compilato localmente**.

```bash
cd ~/progetti/wg-deck
bash scripts/setup_env.sh
bash scripts/build_release.sh
sudo apt install ./dist/wg-deck_1.0.0-2_all.deb
wg-deck --demo
```

APT installa l'app in `/usr/lib/python3/dist-packages/wg_deck`, il comando `/usr/bin/wg-deck`, gli helper in `/usr/lib/wg-deck`, le unità systemd e le policy Polkit. Il launcher compare nel menu applicazioni. Python/Qt vengono aggiornati da APT. **L'installazione abilita automaticamente il publisher in sola lettura e mostra subito i profili esistenti. Non connette/disconnette tunnel e non cambia route.**

## Inventario automatico; restrizione opzionale della privacy

Su un normale desktop Ubuntu con systemd non serve alcun comando aggiuntivo. Il publisher root-owned crea subito snapshot sanitizzati di nomi e traffico con permessi `0644`, leggibili dagli utenti locali. **Contengono metadati di connessione, ma mai chiavi private, endpoint o contenuti delle configurazioni.** Su un sistema multiutente, un amministratore può limitarli al gruppo primario dell'account scelto (`0640`) con:

```bash
sudo wg-deck-setup --restrict-inventory "$USER"
systemctl status wg-deck-inventory.timer
```

Il comando limita la lettura degli snapshot al gruppo primario selezionato e aggiorna il publisher in sola lettura già attivo. Non esegue `wg-quick up` né `wg-quick down`. Per disabilitarlo:

```bash
sudo wg-deck-setup --disable-inventory
```

Leggere configurazioni contenenti chiavi o modificare i profili richiede comunque autorizzazione Polkit. I file WireGuard restano gestiti dal sistema.

## Rimozione e aggiornamento

Prima della disinstallazione disattiva **Start on login**. `sudo apt remove wg-deck` rimuove l'app e ferma il suo publisher. `sudo apt purge wg-deck` elimina anche stato generato e impostazione del gruppo lettore. **Nessuno dei due elimina `/etc/wireguard` o disconnette VPN attive.** Gli aggiornamenti seguono APT e vanno testati con un profilo sacrificabile.

## Sviluppo dai sorgenti (flusso distinto)

```bash
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

Lo script manuale `scripts/install_helper.sh` è destinato all'ambiente di sviluppo. Non eseguirlo con il pacchetto APT presente, perché duplicheresti action ID Polkit e unità systemd. Per le versioni private precedenti consulta [Aggiornamento](UPGRADE.md).

Non disconnettere la VPN necessaria alla tua sessione remota; i test privilegiati vanno eseguiti su un profilo di laboratorio sacrificabile.
