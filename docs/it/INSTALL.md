# Installazione — Italiano

**Destinazione:** desktop Linux con Python 3.12, systemd, Polkit e strumenti WireGuard. Ubuntu/GNOME è il primo ambiente collaudato; altri desktop richiedono verifiche proprie.

## Requisiti

Installa Python 3.12, [uv](https://docs.astral.sh/uv/), `wireguard-tools` (`wg`, `wg-quick`), `iproute2`, Polkit (`pkexec` con agente grafico) e systemd. Per la tray su alcuni GNOME serve supporto StatusNotifier/AppIndicator. **Non avviare la GUI con sudo.**

## Prima la demo — senza privilegi

```bash
git clone https://github.com/matteodurso88/wg-deck.git
cd wg-deck
bash scripts/setup_env.sh
bash scripts/local_gate.sh
bash scripts/run.sh --demo
```

La demo utilizza profili fittizi e non richiede configurazioni VPN.

## Gestione dei profili nativi

Leggi la [guida di sicurezza](SECURITY.md) e il codice in `privileged/`. L'installer richiede esplicitamente `sudo`: copia helper e policy root-owned e abilita il publisher di inventario. Crea `/etc/wireguard` **solo se assente**; non modifica i profili esistenti, non connette/disconnette VPN e non cambia le route.

```bash
bash scripts/install_helper.sh
bash scripts/check_native_inventory.sh
bash scripts/check_native_traffic.sh
bash scripts/run.sh
```

La GUI legge inventario dei **nomi** e contatori non segreti; i contenuti protetti e le operazioni richiedono Polkit quando previsto. I backup `.conf` e ZIP contengono chiavi private: salvali solo in percorsi protetti.

## Launcher e autoavvio facoltativo

```bash
bash scripts/install_desktop.sh
```

Il toggle **Settings → Start on login** crea una voce XDG per l'utente corrente. Avvia **solo la GUI**, non i tunnel. Spostando il checkout, disattiva e riattiva il toggle per aggiornare il percorso. L'autoavvio di una vecchia installazione non viene modificato automaticamente.

## Rimozione e aggiornamenti

```bash
bash scripts/uninstall_desktop.sh
```

Prima di eliminare gli helper privilegiati, leggi gli effetti di `scripts/uninstall_helper.sh`. I profili WireGuard sono file di sistema dell'utente e non vanno cancellati durante la disinstallazione. Dopo modifiche ai sorgenti privilegiati, riesegui i gate prima di reinstallare.

Non disconnettere il tunnel da cui dipende la tua sessione remota. Per le prove distruttive usa soltanto un profilo di laboratorio sacrificabile.
