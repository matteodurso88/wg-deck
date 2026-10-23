# Architettura — Italiano

WG Deck è un'applicazione desktop Python 3.12+ / PySide6. Il `.deb` usa Python e PySide6 6.10+ forniti dalla distribuzione. La GUI non gira come root; le modifiche di sistema sono eseguite mediante helper con funzioni limitate e autorizzazione Polkit esplicita.

```text
GUI PySide6 (src/wg_deck/ui)
    │
    ├── core non privilegiato: modelli, discovery, parser, validazione
    │   ├── /run/wg-deck-profiles.list (root-owned, solo nomi)
    │   └── /run/wg-deck-traffic.tsv (protetto, senza chiavi)
    │
    ├── azioni Polkit separate: read / connect / manage
    │   └── /usr/local/libexec/wg-deck-*
    │        └── wg-quick e systemd per modifiche autorizzate
    │
    └── tray Qt, launcher e autoavvio XDG opzionale

Publisher systemd root-owned: .service + .path + .timer
    └── /etc/wireguard/*.conf (solo nomi e statistiche, mai chiavi)
```

Nel pacchetto Debian gli helper root-owned risiedono in `/usr/lib/wg-deck/`, le policy in `/usr/share/polkit-1/actions/` e le unità in `/usr/lib/systemd/system/`. L'installer manuale di sviluppo usa invece `/usr/local/libexec/`; il builder traduce esplicitamente i percorsi ed esegue controlli. I due modelli d'installazione non devono essere combinati. Il pacchetto Debian abilita automaticamente il publisher in sola lettura sui desktop systemd e rende accessibili gli snapshot sanitizzati root-owned (`0644`) già al primo avvio. Su richiesta si può limitare l'accesso a un gruppo (`0640`) con `sudo wg-deck-setup --restrict-inventory USER`.

La directory di sistema `/etc/wireguard/` è la fonte canonica: nessun registro parallelo dei profili. Le preferenze Qt conservano soltanto opzioni della GUI.

**Identificatori pubblici:** il package Python è wg_deck; helper, policy Polkit e unità systemd usano wg-deck oppure org.matt88.wgdeck. Le installazioni precedenti richiedono la rimozione esplicita dei vecchi helper prima della nuova installazione; profili e tunnel non vengono toccati.

Consulta [sicurezza](SECURITY.md) e `privileged/` per dettagli su permessi e comandi consentiti.
