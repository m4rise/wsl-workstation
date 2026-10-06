# Suivi des configurations globales

[README](../README.md) · [Operations](OPERATIONS.md) · [Maintenance](MAINTENANCE.md)

## Controle courant

```bash
mise run workstation:config-audit
# Après ouverture d'un nouveau shell :
devconfig
# Code de sortie 1 en cas de dérive ou d'état indéterminé :
devconfig --check
# Inventaire local facultatif, sans détecter les modifications :
devconfig --inventory
```

Sans anomalie, le rapport affiche une seule ligne : `Managed configuration is in its desired state.` Sinon il liste les ressources qui demandent une attention. Il s'appuie sur `mise bootstrap status --missing --json`, avec les configurations et capacités réellement actives. Mise contrôle liens, copies, outils, packages, dépôts et services ; le résumé affiche seulement leurs identifiants et statuts, jamais leurs valeurs ou le contenu des fichiers. Pour comprendre une anomalie, lancer localement `mise bootstrap status --missing`, puis comparer avant de réappliquer le bootstrap.

`--inventory` ajoute une liste de configurations locales connues lorsqu'elles existent, même si leur capacité est inactive. Ce sont des pistes de revue, pas des changements détectés. L'inspection de `~/.gitconfig` lit seulement les noms des clés, sans suivre ses inclusions, et affiche des catégories prédéfinies de préférences portables. Le script ne déchiffre pas le bundle et ne modifie aucun fichier.

| Statut | Signification | Action |
| --- | --- | --- |
| `DRIFT` | Une ressource gérée ne correspond pas à l'état désiré | Examiner le statut natif et comparer avant de réappliquer |
| `UNKNOWN` | Le statut d'une ressource ne peut pas être déterminé, par exemple accès à systemd indisponible | Relancer avec les accès normaux du poste et examiner le statut natif |
| `LOCAL` | Configuration présente hors du suivi commun | Choisir entre réglage commun, paramètre local et sauvegarde privée |
| `REVIEW` | Préférences Git locales potentiellement réutilisables ou contrôle manuel nécessaire | Examiner les réglages et intégrer seulement ceux qui sont portables |

Sans `--check`, une anomalie est signalée sans code d'échec. Avec `--check`, une dérive ou un état indéterminé provoque le code 1. Une erreur d'inspection provoque le code 2. `LOCAL` et `REVIEW` n'apparaissent qu'avec `--inventory` ; ils ne provoquent pas d'échec.

Le diagnostic est ponctuel : il ne surveille pas les modifications en arrière-plan, n'est pas une sauvegarde complète et ne prouve pas l'absence de secret. Il ne vérifie pas la configuration effective de chaque application ni les préférences Windows. Les fichiers non listés nécessitent une revue manuelle. `updateall` conserve son rôle de mise à jour des packages et outils ; il ne lance ni collecte de configurations, ni capture privée, ni commit/push.

## Fichiers deja geres

Les liens déclarés dans [le socle](../config.toml) et [la capacité GitHub](../config.github.toml) utilisent les sources suivantes :

| Fichier utilisé | Source dans le dépôt |
| --- | --- |
| `~/.config/git/config` | [Configuration Git commune](../dotfiles/.config/git/config) |
| `~/.zshrc` | [Zsh interactif](../dotfiles/.zshrc) |
| `~/.zprofile` | [Profil Zsh](../dotfiles/.zprofile) |
| `~/.zshenv` | [Environnement Zsh](../dotfiles/.zshenv) |
| `~/.p10k.zsh` | [Powerlevel10k](../dotfiles/.p10k.zsh) |
| `~/.gnupg/gpg-agent.conf` | [Agent GPG](../dotfiles/.gnupg/gpg-agent.conf) |
| `~/.keychainrc` | [Keychain](../dotfiles/.keychainrc), capacité GitHub |

Modifier la cible d'un lien modifie la source du dépôt. Un éditeur ou une application qui remplace le lien par un fichier ordinaire peut rompre ce suivi ; `devconfig` le signale. Aucun changement n'est conservé à distance avant commit et push.

Les ressources déclarées dans [la capacité WSL](../config.wsl.toml) et [la capacité cloud](../config.cloud.toml) sont des copies système. Une modification directe du drop-in `/etc/systemd/system/systemd-binfmt.service.d/override.conf` ou des fichiers du dépôt APT Google Cloud ne remonte pas à sa source. Comparer les copies, reporter le changement voulu dans `system/`, puis réappliquer le bootstrap. Ne pas réappliquer avant d'avoir récupéré une modification locale utile.

Avec `wsl` sélectionné, le bootstrap complet retire aussi les trois artefacts de l'ancien watchdog d'interop via `state = "absent"`. Les étapes d'arrêt du timer et de rechargement/reset ciblé de systemd sont décrites dans [le cycle du bootstrap](ARCHITECTURE.md#cycle-du-bootstrap). WSLInterop reste une ressource native WSL, uniquement vérifiée par le doctor.

## Configurations locales a examiner

| Fichier | Gestion prévue |
| --- | --- |
| `~/.gitconfig` | Préférences portables dans le Git commun ; authentification GitHub CLI recréée par `gh auth login` |
| `~/.config/git/identity.conf`, `allowed_signers` | Identité, signature et confiance locales ; voir le périmètre de récupération ci-dessous |
| `~/.config/git/ignore` | Motifs réutilisables dans un futur dotfile global ; motifs de projet dans son dépôt |
| `~/.ssh/config` | Revoir les règles portables avec [l'exemple SSH](../examples/ssh/config) ; hôtes et chemins personnels en local |
| `~/.codex/config.toml` | Extraire les préférences choisies avec [l'exemple Codex](../examples/codex/config.toml) ; conserver chemins de projets, décisions de confiance et état d'interface en local |
| `~/.codex/AGENTS.md` | Instructions globales réutilisables ; fichier vide sans contenu à intégrer |
| `~/.vscode-server/data/Machine/settings.json` | Revoir les préférences avec [l'exemple VS Code](../examples/vscode/settings.json) ; règles de projet dans `.editorconfig`, Prettier ou ESLint du projet |
| `%APPDATA%/Code/User/settings.json`, `keybindings.json` sous Windows | Gérer séparément via Settings Sync ou une procédure Windows ; ne pas supposer que les préférences WSL les remplacent |
| `~/.config/gh/config.yml` | Préférences et alias CLI réutilisables ; distinguer `hosts.yml` et l'authentification |
| `~/.config/gcloud/configurations/config_default` | Comptes et projets personnels en local ; revoir aussi les autres configurations nommées si tu en crées |
| `~/.docker/config.json` | Intégration Docker Desktop locale ; le fichier peut aussi contenir des identifiants |
| `~/.config/keepassxc/keepassxc.ini` | Préférences indépendantes du coffre ; la capture du KDBX ne les inclut pas |
| `miserc.toml`, `config.local.toml` dans ce dépôt | Sélection de capacités et paramètres du poste, ignorés par Git ; documenter les options nécessaires à une reprise |
| `/etc/wsl.conf` | Activation de systemd à revoir côté WSL ; utilisateur par défaut propre à l'installation |
| `%USERPROFILE%/.wslconfig` sous Windows, si présent | Paramètres de la VM WSL côté hôte, à documenter séparément |
| `~/.npmrc`, `~/.config/pnpm/rc`, `~/.cargo/config.toml`, si présents | Extraire les préférences portables sans jetons de registre ni chemins personnels |
| `~/.aws`, `~/.azure` | Paramètres et sessions de comptes ; peuvent pointer vers Windows ; hors du bundle actuel |

Les exemples sont des références, pas des ressources déployées. Fusionner seulement les réglages voulus dans une configuration existante. Ne pas remplacer intégralement un fichier local par un exemple : cela pourrait effacer des règles SSH, des serveurs MCP ou des préférences utiles. Pour SSH, adapter `IdentityFile` à la clé réellement utilisée. Pour VS Code, les réglages Prettier supposent que l'extension est installée.

Codex conserve ses préférences utilisateur dans `~/.codex/config.toml` ; les configurations de projet et les politiques administrées peuvent influer sur les valeurs effectives. Voir [la documentation officielle](https://learn.chatgpt.com/docs/config-file/config-basic) et [les instructions globales](https://learn.chatgpt.com/docs/agent-configuration/agents-md). Le fichier `config.codex.toml` de ce dépôt sélectionne une capacité mise : ce n'est pas le fichier de préférences de Codex.

## Integrer un changement

1. Lancer `devconfig --inventory` et examiner localement le fichier concerné. Pour Git, `git config --show-origin --get rerere.enabled` identifie la source effective sans afficher toute la configuration.
2. Mettre un réglage réutilisable dans sa source existante. Pour un nouveau dotfile, ajouter une source sans données personnelles et sa déclaration `[dotfiles]` dans la capacité appropriée. Garder les valeurs propres au poste dans un fichier local ou une procédure de paramétrage.
3. Si le fichier local n'est pas encore géré, comparer et conserver une copie privée avant d'installer un lien. Ne pas copier sa totalité dans le dépôt par défaut. Pour une nouvelle ressource déployée, valider aussi un bootstrap dans une WSL jetable et un second passage sans dérive.
4. Relire les fichiers nouveaux et le diff, puis valider :

```bash
git status --short
git diff
mise -E secrets install --locked
mise run workstation:check
```

Créer ensuite un commit ciblé et le pousser selon le parcours de [maintenance](MAINTENANCE.md#validation). Ne pas publier de sortie complète de configuration contenant comptes, chemins personnels ou identifiants.

`rerere.enabled = true` appartient maintenant au Git commun. Si une ancienne entrée identique subsiste dans `~/.gitconfig`, elle est redondante. Après vérification locale de sa valeur, son retrait facultatif se fait ainsi :

```bash
git config --file "$HOME/.gitconfig" --get-all rerere.enabled
# Retirer uniquement l'ancienne valeur true ; conserver une surcharge false voulue.
git config --file "$HOME/.gitconfig" --fixed-value --unset-all rerere.enabled true
git config --show-origin --get rerere.enabled
```

La commande de retrait échoue si aucune valeur correspondante n'existe ; cela n'indique pas que le Git commun est désactivé. `rerere` conserve ses résolutions dans chaque dépôt de travail : activer cette préférence ne sauvegarde pas leurs caches `.git/rr-cache`.

## Perimetre de la sauvegarde privee

`secrets:capture` sauvegarde le nom et l'e-mail Git effectifs, les entrées de clé SSH explicitement fournies et, pour une première inclusion, un coffre KDBX. Une restauration SSH reconstruit les paramètres de signature prévus. La mise à jour ultérieure du coffre utilise `secrets:vault-update`. Voir [le parcours complet](OPERATIONS.md#bundle-prive).

Ces commandes ne sauvegardent pas intégralement `~/.gitconfig`, `identity.conf`, `~/.ssh/config`, les préférences Codex/VS Code/KeePassXC, le sélecteur mise ou les configurations Windows. Une personnalisation conservée seulement en local demande une procédure de recréation ou une sauvegarde privée distincte. Le format actuel du bundle n'accepte pas des entrées arbitraires de configuration.

La clé age doit rester séparée du bundle avec ses sauvegardes hors ligne. Les clés SSH sont chiffrées par le parcours prévu, le KDBX conserve son propre chiffrement. Les sessions, jetons, historiques, caches et clés de déchiffrement ne doivent pas être importés dans les dotfiles communs.
