# Aggiornamento dall'installazione privata di sviluppo

WG Deck v1.0.0 utilizza identificatori tecnici pubblici coerenti. La precedente build privata ha installato servizi, desktop entry e policy Polkit con una denominazione precedente. **Non cancellare /etc/wireguard e non disconnettere i tunnel attivi durante il passaggio.**

1. Chiudi completamente la vecchia GUI WG Deck, inclusa la tray. Se era attivo **Start on login**, disabilitalo e verificane lo stato.
2. Nel **precedente checkout privato WORKSHOP**, esamina ed esegui `bash scripts/uninstall_desktop.sh` come utente desktop. Rimuove soltanto l'integrazione desktop gestita dalla vecchia versione.
3. Nel medesimo checkout, esamina `scripts/uninstall_helper.sh` e avvialo esplicitamente. Disabilita il vecchio publisher d'inventario e rimuove esclusivamente helper/policy/unità della vecchia app; **non** elimina configurazioni WireGuard, non modifica route e non disconnette i tunnel.
4. Nel **nuovo checkout** `~/progetti/wg-deck`, esegui il gate locale e installa consapevolmente `bash scripts/install_helper.sh` e `bash scripts/install_desktop.sh`. L'autoavvio utente rimane facoltativo.
5. Verifica un profilo sacrificabile tramite gli smoke nativi e controlla la tray GNOME. Non intervenire sulla VPN da cui dipende una connessione remota.

**Non tenere contemporaneamente attivi i publisher vecchio e nuovo.** Conserva il branch WORKSHOP finché non è completo il collaudo. Il tool di rinomina del repository non modifica il sistema né i file root-owned.
