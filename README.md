# Workstation bootstrap

Une workstation de développement **Ubuntu 26.04 sous WSL2, x86-64**, installée et maintenue avec `mise`. Le dépôt fournit le shell, les CLI, les packages Ubuntu et les contrôles. Les comptes, identités et secrets appartiennent à chaque utilisateur. La version minimale de mise figure dans `min_version` de `config.toml`.

`mise bootstrap --update --locked` reste le point d'entrée. Les dotfiles sont gérés par mise ; les approches de [chezmoi](https://www.chezmoi.io/) et [Omakub](https://omakub.org/) inspirent la séparation des données locales et les choix explicites, sans ajouter un second orchestrateur.

## Installation neuve

Ce parcours concerne un nouveau compte Linux. Si `~/.config/mise` ou des dotfiles Zsh existent déjà, conserver une sauvegarde privée et examiner les différences avant le bootstrap. Pour maintenir une installation de ce projet, suivre [Maintenance](docs/MAINTENANCE.md).

Dans un terminal PowerShell administrateur, installer Ubuntu 26.04 avec WSL2, redémarrer si Windows le demande, puis ouvrir Ubuntu et créer son utilisateur Linux. Docker Desktop et VS Code restent des applications Windows ; leur intégration est facultative.

```powershell
wsl --install --distribution Ubuntu-26.04
```

Dans le terminal Ubuntu en Bash, exécuter les commandes dans l'ordre et s'arrêter à la première erreur. Saisir la référence GitHub du dépôt choisi, au format `OWNER/REPOSITORY` visible dans son URL, ou celle d'un fork public. Le clone HTTPS public ne demande pas de compte GitHub.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3
read -r -p 'Dépôt GitHub (OWNER/REPOSITORY) : ' public_repo
git clone "https://github.com/$public_repo.git" "$HOME/.config/mise"
cd "$HOME/.config/mise"
python3 scripts/install-mise.py
export PATH="$HOME/.local/bin:$PATH"
mise --version
mise trust
mise bootstrap --update --locked
exec zsh -l
```

Le profil générique installe les outils communs et configure Zsh/Oh My Zsh/Powerlevel10k. Il ne demande aucun compte personnel. La modification du shell de connexion peut demander ton mot de passe Ubuntu.

L'installateur vérifie l'empreinte du script mise avec `system/bootstrap/mise.json` avant de l'exécuter. Il conserve une version existante qui satisfait le minimum. `mise trust` autorise l'exécution de cette configuration : relire les sources avant de lui faire confiance. APT peut également demander le mot de passe Ubuntu. Vérifier ensuite :

```bash
mise run workstation:doctor --bootstrap
mise run workstation:config-audit --check
```

Pour reprendre aussi les commits shell du snapshot, remplacer **le premier bootstrap** par `mise -E reproducible bootstrap --update --locked`. Cet environnement est temporaire et ne doit pas être enregistré dans `miserc.toml`. Les futures mises à jour restent disponibles. Voir [reproductibilité](docs/MAINTENANCE.md#reproductibilite).

## Capacites optionnelles

La sélection utilise les environnements natifs mise, enregistrés dans `miserc.toml`, ignoré par Git. Elle s'applique aussi aux commandes lancées depuis d'autres répertoires. Ne pas fixer `MISE_GLOBAL_CONFIG_FILE` : cela empêche la découverte des variantes globales avec la version mise utilisée ici.

| Capacité | Effet |
| --- | --- |
| `github` | GitHub CLI, Keychain, plugin shell et contrôle des accès |
| `cloud` | Dépôt APT Google, Google Cloud CLI, plugin et diagnostic |
| `codex` | Installation officielle de Codex et maintenance |
| `docker` | Diagnostic et alias Docker Desktop ; aucun moteur Linux installé |
| `wsl` | Compatibilité Ubuntu/WSL, validation WSLInterop et adaptation systemd-binfmt |
| `secrets` | fnox + age et commandes de sauvegarde/restauration |
| `vault` | KeePassXC via APT ; CLI utilisable sans écran, interface graphique facultative avec WSLg |

```bash
mise run profile:select wsl github
mise bootstrap --update --locked

# Toutes les capacités du setup personnel, dont la restauration et KeePassXC.
mise run profile:select personal
mise bootstrap --update --locked

# Revenir à la sélection générique.
mise run profile:select generic
```

La sélection ne désinstalle pas les outils et ne supprime pas les services déjà installés. Pour une session temporaire : `mise -E wsl,github bootstrap --update --locked`. La sélection personnelle conserve la capacité `wsl` : WSL gère nativement WSLInterop, le doctor valide son état et le bootstrap empêche `systemd-binfmt` de s'exécuter sous WSL. Il retire aussi les anciens fichiers et le watchdog d'interop.

## Identite et restauration

Le Git commun inclut `~/.config/git/identity.conf` si ce fichier existe. La [procédure d'identité](docs/OPERATIONS.md#identite-git-et-ssh) explique comment créer une nouvelle clé et comment configurer une identité publique distincte avec adresse *noreply*.

Le parcours facultatif restaure une identité et, sur demande, une clé SSH et un coffre KeePassXC depuis un **dépôt privé chiffré**. Il utilise une clé age récupérée séparément. Les sessions GitHub, Google Cloud et Codex sont recréées par leurs connexions natives. Voir [première sauvegarde et reprise complète](docs/OPERATIONS.md#bundle-prive).

## Commandes quotidiennes

| Alias | Commande |
| --- | --- |
| `devprofile` | `mise run profile:select` |
| `devrestore` | `mise run secrets:restore` |
| `devvaultupdate` | `mise run secrets:vault-update`, si `secrets` et `vault` sont actives |
| `devdoctor` | `mise run workstation:doctor` |
| `devconfig` | `mise run workstation:config-audit`, anomalies des ressources gérées |
| `devcheck` | `mise run workstation:check`, lint, secrets et tests |
| `devlint` | `mise run workstation:lint` |
| `devaudit` | `mise run security:audit` |
| `devversions` | `mise run workstation:versions` |
| `sysupdate` | `mise run system:update` |
| `devupdate` | `mise run dev:update` puis nouveau shell |
| `devclean` | `mise run dev:clean` |
| `updateall` | Mise à jour système + développement puis nouveau shell |
| `dockerclean` | Nettoyage Docker sans volumes, si capacité active |
| `sshunlock` | Déverrouillage de la clé locale via Keychain, si capacité active |

`devdoctor --bootstrap` contrôle le provisionnement sans demander de comptes, d'agent SSH déverrouillé ni Docker Desktop. Le diagnostic normal vérifie les intégrations personnelles activées.

`devconfig` résume l'état natif du bootstrap. `devconfig --check` échoue en cas de dérive ou d'état indéterminé. `devconfig --inventory` ajoute les fichiers locaux à examiner ; leur présence n'indique pas une modification. Voir [les fichiers à surveiller et leur intégration](docs/CONFIGURATION.md). `updateall` ne capture pas les configurations et ne crée aucun commit.

## Verification et publication

Pour contrôler un changement, y compris sur le profil générique :

```bash
mise -E secrets install --locked
mise run workstation:check
```

`-E secrets` ajoute les outils cryptographiques pour cette commande sans changer le profil enregistré. Les tests utilisent des données fictives et des répertoires temporaires ; ils ne restaurent rien dans le compte courant.

La CI applique ces contrôles sur Ubuntu 26.04, exporte le commit et teste les sources exportées. Un second job installe **cet export dans une vraie distribution Ubuntu 26.04 WSL** sur Windows : bootstrap générique avec snapshot shell, migration d'un timer legacy inerte, activation des capacités personnelles, seconde application puis contrôle de convergence et WSLInterop. Après un `wsl --shutdown`, une nouvelle invocation vérifie un identifiant de boot différent, systemd `running`, `systemd-binfmt` inactive/skipped et l'exécution de CMD et PowerShell. Docker Desktop, les véritables comptes et l'ouverture graphique du coffre restent à valider sur le poste. La CI se déclenche sur les PR, `main`, chaque semaine et manuellement.

La reproductibilité concerne la configuration, les CLI verrouillées et, sur demande, les commits shell. Les packages APT et l'installateur Codex évoluent : cette configuration ne produit pas une image système identique octet par octet.

La publication se prépare dans un nouveau dépôt à historique vide. Le dépôt privé d'origine conserve son historique. [Procédure de publication](docs/MAINTENANCE.md#publication).

- [Architecture](docs/ARCHITECTURE.md)
- [Opérations et récupération](docs/OPERATIONS.md)
- [Outils](docs/TOOLS.md)
- [Maintenance, tests et publication](docs/MAINTENANCE.md)
- [Validation pas à pas](docs/VALIDATION.md)
- [Contribution](CONTRIBUTING.md)
- [Sécurité](SECURITY.md)

Licence [MIT](LICENSE). Les outils installés gardent leurs licences respectives.
