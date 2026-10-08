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
| `wsl` | Interop Windows native et condition systemd-binfmt | Sources versionnées |
| `secrets` | fnox, age et age-keygen | `mise.secrets.lock` |
| `vault` | KeePassXC complet, keepassxc-cli | APT Ubuntu |

### Codex dans VS Code Agents (WSL)

La combinaison des capacités `codex` et `wsl` crée le lien `~/.local/share/vscode-codex-sdk/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex` vers `~/.local/bin/codex`. Le bootstrap et `codex:update` valident ce lien à chaque passage. Aucune seconde installation npm n'est nécessaire.

Le `~/.zprofile` géré par mise expose `VSCODE_AGENT_HOST_CODEX_SDK_ROOT` lorsque le lien est valide. VS Code Agent Host peut ainsi lancer le même CLI standalone, mais cette surcharge relève d'une API interne expérimentale : versions, structure et protocole peuvent évoluer. Le fournisseur `vscode-proxy` peut également filtrer les modèles indépendamment de la version du CLI.

Après mise à jour, démarrer une nouvelle session Agent Host : les processus existants ne se mettent pas à jour à chaud. Contrôles : `mise run codex:install`, `mise run workstation:doctor`, `zsh -lc 'printenv VSCODE_AGENT_HOST_CODEX_SDK_ROOT'`, puis `pgrep -af 'codex.*app-server'` pendant une session Codex Agents active.

Pour revenir au SDK géré par VS Code, retirer uniquement le lien symbolique généré sous `~/.local/share/vscode-codex-sdk` et redémarrer Agent Host ; `.zprofile` cesse alors d'exporter la variable. Nettoyer séparément toute injection manuelle antérieure dans `server-env-setup` ou `WSLENV` si elle existe, sans toucher aux autres réglages.

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
