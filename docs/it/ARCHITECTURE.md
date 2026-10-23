# Architettura — Italiano

WG Deck è un'applicazione desktop Python 3.12 / PySide6. La GUI non gira come root; le modifiche di sistema sono eseguite mediante helper con funzioni limitate e autorizzazione Polkit esplicita.

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

La directory di sistema `/etc/wireguard/` è la fonte canonica: nessun registro parallelo dei profili. Le preferenze Qt conservano soltanto opzioni della GUI.

**Identificatori pubblici:** il package Python è wg_deck; helper, policy Polkit e unità systemd usano wg-deck oppure org.matt88.wgdeck. Le installazioni precedenti richiedono la rimozione esplicita dei vecchi helper prima della nuova installazione; profili e tunnel non vengono toccati.

Consulta [sicurezza](SECURITY.md) e `privileged/` per dettagli su permessi e comandi consentiti.
