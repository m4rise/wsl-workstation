# Politique WSL et migration

[README](../README.md) · [Opérations](OPERATIONS.md) · [Validation](VALIDATION.md) · [CI locale](CI-LOCAL.md)

Ce parcours concerne Ubuntu 26.04 sous WSL2, avec systemd actif et la capacité `wsl` sélectionnée. Il s'applique à une installation de ce dépôt, y compris à un poste qui utilisait l'ancien watchdog d'interop.

## État attendu

WSL gère nativement WSLInterop. Le dépôt vérifie son bon fonctionnement ; il ne réenregistre aucun handler. WSL protège le registre binfmt partagé : le drop-in empêche `systemd-binfmt` de tenter de le flusher et d'échouer sous WSL.

| Contrôle | Résultat attendu |
| --- | --- |
| Capacité | `wsl` active et `WORKSTATION_WSL=1` |
| `/usr/local/sbin/ensure-wsl-interop` | Absent |
| `/etc/systemd/system/wsl-interop-fix.service` | Absent |
| `/etc/systemd/system/wsl-interop-fix.timer` | Absent |
| `/etc/systemd/system/systemd-binfmt.service.d/override.conf` | `[Unit]` puis `ConditionVirtualization=!wsl` |
| `systemd-binfmt.service` | Chargé avec le drop-in, inactive/skipped, jamais failed |
| `/proc/sys/fs/binfmt_misc/WSLInterop` | Lisible, `enabled`, `interpreter /init`, `flags: PF` |
| CMD et PowerShell | Exécutables depuis `/mnt/c` |
| Bootstrap | Deux passages convergent, `config-audit --check` réussit |
| Systemd | `running`, aucune unité failed |

## 1. Examiner le poste

Dans Ubuntu, depuis le checkout contenant les sources à appliquer :

```bash
cd "$HOME/.config/mise"
git status --short
mise config ls
ps -p 1 -o comm=
mise exec -- bash -c 'test "${WORKSTATION_WSL:-0}" = 1'
mise run workstation:config-audit --check
mise run workstation:doctor --bootstrap
systemctl is-system-running
systemctl --failed --no-pager
```

PID 1 doit être `systemd`. Si le contrôle de capacité échoue, choisir les capacités voulues selon [le README](../README.md#capacites-optionnelles). `profile:select` remplace la liste active : conserver les autres capacités souhaitées ; `personal` inclut `wsl`. Sur une ancienne installation, le doctor et l'audit peuvent échouer ici parce que la migration reste à appliquer. Lire leurs anomalies avant de poursuivre.

Si l'audit, le doctor et l'état systemd sont déjà conformes, passer au contrôle après redémarrage. Une configuration déjà convergée ne nécessite pas de réinstallation.

## 2. Appliquer la migration si nécessaire

Récupérer d'abord la version choisie des sources selon [Maintenance](MAINTENANCE.md#utiliser-le-depot-public). Examiner et préserver toute modification utile des copies système avant leur remplacement. Dans Ubuntu, appliquer une commande à la fois et s'arrêter en cas d'échec :

```bash
cd "$HOME/.config/mise"
mise bootstrap --locked
mise bootstrap --locked
mise bootstrap status --missing
mise run workstation:config-audit --check
mise run workstation:doctor --bootstrap
systemctl is-system-running
systemctl --failed --no-pager
```

Le premier passage arrête/désactive le timer legacy, arrête une éventuelle exécution de son service, retire les trois fichiers via mise et installe le répertoire et le drop-in. La tâche finale recharge systemd si nécessaire et nettoie uniquement l'échec historique éventuel de `systemd-binfmt.service`. Le second passage doit laisser ces ressources inchangées.

`--locked` reprend les versions des outils verrouillées. Pour une installation neuve ou une actualisation volontaire des index APT et des dépôts shell, le parcours général utilise `mise bootstrap --update --locked`. Une simple migration d'un poste installé peut utiliser les commandes ci-dessus. `bootstrap files apply` seul ne lance pas les étapes de cycle de vie nécessaires à cette migration.

## 3. Verifier apres un shutdown complet

Enregistrer le travail en cours avant cette étape : `wsl --shutdown` arrête toutes les distributions et la VM WSL, y compris les processus de travail et les services liés à Docker Desktop. Exécuter ces commandes dans **PowerShell Windows**, puis rouvrir la distribution. Adapter le nom si elle porte un autre nom :

```powershell
wsl --list --verbose
wsl --shutdown
wsl --distribution Ubuntu-26.04
```

Dans le nouveau terminal Ubuntu :

```bash
cd "$HOME/.config/mise"
systemctl is-system-running
systemctl --failed --no-pager
systemctl status systemd-binfmt.service --no-pager
cat /etc/systemd/system/systemd-binfmt.service.d/override.conf
cat /proc/sys/fs/binfmt_misc/WSLInterop
(cd /mnt/c && cmd.exe /d /c 'exit 0')
(cd /mnt/c && powershell.exe -NoProfile -Command 'exit 0')
mise run workstation:config-audit --check
mise run workstation:doctor --bootstrap
```

Systemd doit afficher `running`. Le statut de `systemd-binfmt` doit montrer `inactive (dead)` et `ConditionVirtualization=!wsl was not met`. **`systemctl status` renvoie normalement 3 pour ce service inactif** : lire cet état et poursuivre les autres contrôles. Ses anciens messages de journal peuvent encore mentionner un échec ; le champ `Active` et la condition du démarrage courant déterminent l'état actuel.

Ne pas réappliquer le bootstrap avant ces contrôles : ils doivent démontrer que la configuration fonctionne au nouveau démarrage. Pour le diagnostic personnel complet, déverrouiller l'agent avec `sshunlock` si la capacité GitHub est active, puis lancer `mise run workstation:doctor`. Les connexions des comptes suivent [Opérations](OPERATIONS.md#connexions-natives-et-controle-final).

## 4. Comprendre un échec

Si systemd reste `degraded`, examiner `systemctl --failed --no-pager`. L'override WSL traite uniquement `systemd-binfmt` : un échec d'une autre unité exige son propre diagnostic. Ne pas effacer globalement les échecs pour obtenir artificiellement un état sain.

Si WSLInterop est absent ou invalide, conserver les résultats de ces contrôles et examiner la version et la configuration WSL côté Windows. Le dépôt ne propose pas de watchdog ou de réenregistrement en secours. Le futur retrait de l'override devra être validé dans la vraie CI WSL, avec un nouveau boot de la VM et l'exécution Windows fonctionnelle.
