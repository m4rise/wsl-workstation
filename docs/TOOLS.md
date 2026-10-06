# Outils

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Operations](OPERATIONS.md) · [Maintenance](MAINTENANCE.md)

## Socle commun

Les versions exactes viennent de `mise.lock`. Node et pnpm suivent une version majeure ; les autres sélecteurs sont `latest`, résolus et contrôlés dans le lockfile. Utiliser `mise install --locked` pour reprendre ces versions.

| Outil | Usage |
| --- | --- |
| Node / pnpm | Runtime JavaScript et gestionnaire de packages ; chaque projet garde ses propres contraintes |
| fzf | Recherche interactive et sélection shell |
| bat | Affichage avec coloration ; `rcat` conserve le `cat` système |
| ripgrep / fd | Recherche de contenu et de fichiers |
| delta | Pager Git, diff interactif |
| difftastic | Diff structurel, via `git ddiff`, `git dshow`, `git dlog` |
| shellcheck / shfmt | Analyse et formatage des scripts shell |
| yq | Requêtes YAML ; jq système pour JSON |
| actionlint | Vérification GitHub Actions |
| trivy | Analyse ponctuelle de projets et d'images |
| gitleaks | Recherche de secrets dans l'historique et les fichiers |
| lychee | Contrôle hors ligne des liens et ancres Markdown |
| Ruff | Analyse et formatage Python, sans dépendance Python externe |
| taplo | Validation TOML et vérification du formatage |
| zoxide | Navigation shell dans les répertoires |
| hyperfine | Mesures répétées de commandes |
| eza / dua | Listes de fichiers et usage disque |

APT fournit les prérequis système : certificats, curl, Git, OpenSSH, Zsh, outils de compilation, Python, archives, jq, rsync, make, OpenSSL, mkcert, GnuPG et pinentry. Aucune autorité mkcert personnelle n'est copiée par le bootstrap.

## Capacites

| Capacité | Outils / intégration | Version |
| --- | --- | --- |
| `github` | gh, Keychain | `mise.github.lock` |
| `cloud` | gcloud et dépôt APT Google | Package Ubuntu/Google courant |
| `codex` | Codex CLI | Installateur officiel, mise à jour explicite |
| `docker` | CLI fournie par Docker Desktop, Compose | Hôte Windows |
| `wsl` | Validation WSLInterop natif et drop-in systemd-binfmt | Sources versionnées |
| `secrets` | fnox, age et age-keygen | `mise.secrets.lock` |
| `vault` | KeePassXC complet, keepassxc-cli | APT Ubuntu |

Le profil secrets utilise le backend explicite `github:jdx/fnox` et le backend aqua d'age. Les URL, empreintes et provenances sont dans le lockfile. `fnox` gère le chiffrement des entrées ; `age-keygen` crée une identité indépendante. Les tâches ne mettent pas les secrets dans l'environnement global.

KeePassXC stocke les mots de passe humains dans un fichier chiffré. Son interface graphique nécessite WSLg ; `keepassxc-cli` crée, ouvre et modifie les coffres sans écran ni WSLg. Le paquet Ubuntu `keepassxc-full` inclut toutefois les bibliothèques Qt et l'application graphique : « sans interface » décrit l'exécution de la CLI, pas un paquet sans dépendances graphiques. Aucun mot de passe maître n'est transmis par argument de commande ou enregistré dans la configuration du projet. Voir [utilisation en terminal](OPERATIONS.md#keepassxc-sans-interface).

`secrets:vault-update` sauvegarde l'ancien KDBX hors du bundle et remplace atomiquement le snapshot après contrôle de son en-tête. La véritable ouverture reste un contrôle manuel avec le mot de passe maître.

## Compositions utiles

```bash
rg 'pattern' .
fd '\.toml$'
fd --type f | fzf
jq '.scripts' package.json
yq '.services' compose.yaml
hyperfine --warmup 2 'commande-a' 'commande-b'
mise run security:scan .
```

Pour les agents et les journaux, préférer une sortie lisible sans pager :

```bash
git --no-pager diff
git --no-pager diff --stat
git ddiff
```

Ne pas définir globalement `diff.external` : cela perturbe certains éditeurs et outils. Les alias structurels sont ponctuels. Ne pas afficher `fnox get`, `fnox export`, `mise env` ou un cache d'authentification dans un journal partagé lorsque des secrets sont chargés.

## Controles du depot

```bash
mise -E secrets install --locked
mise run workstation:check
```

Gitleaks masque les valeurs ; une alerte réelle impose une révocation, pas seulement une suppression du fichier. Lychee hors ligne ne vérifie pas la disponibilité HTTP des sites externes. La validation TOML ne remplace pas un test du bootstrap. Une exception de scanner doit être étroite, expliquée et limitée à un faux positif établi.

Les connexions et commandes opérationnelles détaillées sont dans [Operations](OPERATIONS.md).
