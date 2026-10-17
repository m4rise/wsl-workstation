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
| `codex` | Codex standalone officiel, helper associé et Bubblewrap ; avec `wsl`, SDK Agent Host lié au CLI |
| `docker` | Diagnostic et alias Docker Desktop ; aucun moteur Linux installé |
| `wsl` | Session systemd utilisateur, interop Windows native et adaptation systemd-binfmt |
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

L'association `codex` + `wsl` configure le SDK Codex Agent Host pour réutiliser le standalone. Voir [Outils](docs/TOOLS.md#codex-dans-vs-code-agents-wsl).

`profile:select` **remplace la sélection active** : fournir toutes les capacités souhaitées, y compris celles à conserver. La sélection ne désinstalle pas les outils déjà installés. Pour une session temporaire : `mise -E wsl,github bootstrap --update --locked`. `personal` inclut `wsl`. WSL gère l'interop Windows nativement ; cette capacité installe la session DBus/PAM utilisateur et une condition systemd qui empêche `systemd-binfmt` d'échouer sur le registre protégé par WSL. Après son premier bootstrap, enregistrer le travail puis lancer `wsl --shutdown` dans PowerShell Windows et rouvrir Ubuntu : cela arrête toutes les distributions WSL et applique la condition au prochain démarrage. `mise run workstation:doctor --bootstrap` vérifie ensuite l'exécution Windows.

## Prerequis communs pour une boucle agentique

Après l'installation neuve ci-dessus, sélectionner les trois capacités existantes puis réappliquer le même bootstrap :

```bash
# Remplace la sélection : ajouter ici les autres capacités à conserver.
mise run profile:select codex wsl docker
mise bootstrap --update --locked
exec zsh -l
```

Le socle fournit Node via mise et `libatomic1`. `codex` ajoute Bubblewrap et le standalone officiel avec son helper `codex-code-mode-host` ; `wsl` ajoute `dbus-user-session`, qui dépend de `libpam-systemd`. Aucun moteur Docker Linux n'est installé.

Sur Windows, garder WSL à jour (`wsl --update`), vérifier `wsl --list --verbose` et installer/démarrer Docker Desktop avec le moteur WSL2 et les conteneurs Linux. Dans **Settings > Resources > WSL Integration**, activer cette distribution puis appliquer. Vérifier que systemd est actif dans Ubuntu ; si nécessaire, ajouter `[boot]` avec `systemd=true` à `/etc/wsl.conf` en conservant les autres réglages. Enregistrer le travail, lancer `wsl --shutdown` depuis PowerShell puis rouvrir Ubuntu sous son utilisateur Linux ordinaire. L'interop Windows doit rester active. Voir les guides [systemd dans WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd) et [Docker Desktop WSL2](https://docs.docker.com/desktop/features/wsl/).

```bash
# Provisionnement général, sans comptes ni obligation de démarrer Docker Desktop.
mise run workstation:doctor --bootstrap
# Prérequis communs obligatoires, sans connexion à un modèle ni inférence.
mise run workstation:doctor --agentic
```

Le second contrôle échoue si une capacité requise est inactive ou si Ubuntu/architecture/WSL2, Node, Bubblewrap, le standalone/helper Codex, systemd utilisateur, les contrôleurs cgroup v2 `cpu memory pids`, l'interop ou Docker Desktop/Compose sont incompatibles. Il lance uniquement des sondes locales : namespaces Bubblewrap et unité utilisateur transitoire avec limites CPU/mémoire/processus. Chaque refus indique une piste de correction. Exécuter le diagnostic dans un terminal WSL normal : une sandbox d'agent peut bloquer ces sondes et ne valide alors pas l'hôte. Ne pas désactiver une frontière pour obtenir un succès. Détails : [diagnostic et dépendances](docs/TOOLS.md#diagnostic-des-prerequis-communs).

Les mises à jour restent explicites avec `mise run codex:update`, `updateall` et les mécanismes mise existants. Node suit sa majeure courante déclarée et le lockfile évolue ; aucune ancienne version Codex ou Node n'est imposée à demeure. Après mise à jour, relancer le diagnostic et les validations du projet consommateur. Workstation prépare le poste ; `m4rise/sulu-cms-platform` reste propriétaire de sa boucle, de ses permissions, frontières, oracles et validations. Un doctor vert ne valide pas le lot 2 Sulu.

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

La CI applique ces contrôles sur Ubuntu 26.04, exporte le commit et teste les sources exportées. Un second job installe **cet export dans une vraie distribution Ubuntu 26.04 WSL** sur Windows : bootstrap générique avec snapshot shell, composition `codex wsl docker`, activation des capacités personnelles, applications répétées et contrôle de convergence. Après un `wsl --shutdown`, elle vérifie que systemd est opérationnel et relance le doctor. Docker Desktop, les véritables comptes et l'ouverture graphique du coffre restent à valider sur le poste. La CI se déclenche sur les PR, `main`, chaque semaine et manuellement.

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
