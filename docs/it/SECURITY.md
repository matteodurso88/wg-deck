# Modello di sicurezza — Italiano

La GUI Qt di WG Deck non gira come root. Solo helper installati in percorsi **root-owned**, con comandi consentiti esplicitamente, eseguono operazioni di sistema. I file WireGuard sono sensibili e possono contenere hook eseguibili da `wg-quick`.

## Separazione dei privilegi

- **Read** (azione Polkit separata): lettura/export dei contenuti; il sistema può riutilizzare brevemente l'autorizzazione.
- **Connection** (azione separata): `up/down` con controlli e conferma UI facoltativa; possibile cache Polkit breve.
- **Manage**: creazione, sostituzione, import ZIP ed eliminazione con `auth_admin` per ogni operazione.
- **Publisher inventario**: servizio/path/timer systemd root-owned, che espone in `/run` solo nomi nativi e dati RX/TX/handshake limitati, senza chiavi.

## Difese

I nomi sono validati; la scrittura rifiuta symlink e collisioni e usa permessi `0600`, backup protetti, confronto revisioni e sostituzioni atomiche quando opportuno. Hook/direttive non supportate non vengono riscritte silenziosamente. L'autoavvio utente non connette VPN. Le chiavi non vanno mai in log, screenshot, storico Git o issue.

## Packaging Debian e attivazione esplicita

Il pacchetto Debian installa helper root-owned in `/usr/lib/wg-deck/` e policy Polkit in `/usr/share/polkit-1/actions/`. L'installazione non avvia VPN né abilita l'inventario. Solo il comando esplicito `sudo wg-deck-setup --enable-inventory USER` configura il gruppo primario autorizzato alla lettura e avvia il publisher in sola lettura. Gli appartenenti a tale gruppo possono vedere i nomi delle interfacce e le statistiche aggregate: scegliere attentamente l'account. La rimozione e il purge APT non modificano `/etc/wireguard/`. Non mischiare gli helper di sviluppo in `/usr/local/libexec` con il pacchetto APT.

## Rischi residui

- Un file `.conf` **già esistente** può contenere `PreUp`, `PostUp`, `PreDown`, `PostDown`: `wg-quick` può eseguirli con privilegi elevati. Non connettere profili sconosciuti.
- L'export rende accessibili le chiavi all'utente autenticato: ZIP e configurazioni vanno custoditi.
- Interfaccia UP e handshake sono indicatori diversi.
- Esamina lo script d'installazione prima di concedere `sudo`. I test Qt demo non dimostrano la sicurezza dei privilegi.
- Dipendenze Qt, librerie native e packaging richiedono audit prima di rilasciare binari.

Segnala vulnerabilità privatamente secondo [SECURITY.md](../../SECURITY.md).
