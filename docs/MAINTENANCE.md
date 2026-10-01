# Maintenance

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Operations](OPERATIONS.md) · [Tools](TOOLS.md)

## Faire evoluer le depot

La documentation est le parcours de validation. Toute commande nécessaire qui diffère du guide doit entraîner sa correction dans le même changement, puis une nouvelle exécution du parcours. Les commandes de ce guide se lancent depuis `~/.config/mise`, sauf indication contraire.

Choisir la responsabilité : CLI portable dans mise, package système dans APT, intégration Windows documentée côté hôte. Placer un outil facultatif dans sa capacité et adapter ensemble bootstrap, shell, `doctor`, tests et documentation. Une nouvelle capacité reste absente de la sélection générique. Les exemples ne sont pas déployés automatiquement.

Conserver les personnalisations dans `miserc.toml`, `config.local.toml`, l'identité Git locale ou le bundle privé. Les dotfiles communs ne contiennent ni identité privée, ni chemin propre à une personne. Ne pas définir `MISE_GLOBAL_CONFIG_FILE` : cela empêche la découverte des variantes globales avec la version mise de référence. `mise config ls` montre les sources réellement chargées.

Pour intégrer une préférence ou une copie système modifiée, suivre [Configuration](CONFIGURATION.md). Examiner les différences avant de réappliquer le bootstrap, car une copie locale utile pourrait être remplacée. Un lien sain ne prouve pas que les modifications de sa source ont été commitées : vérifier aussi `git status` et `git diff`.

## Utiliser le depot public

Le même clone public peut servir au poste personnel et aux contributions. Les capacités restent choisies dans `miserc.toml`, les paramètres du poste dans `config.local.toml`, et les comptes, clés et préférences personnelles restent locaux. `updateall` conserve son fonctionnement. Configurer l'[identité publique au niveau de ce clone](OPERATIONS.md#identite-git-et-ssh) pour garder l'identité globale des autres projets.

Pour le mainteneur ayant accès en écriture au dépôt, `origin` désigne le projet public. Les autres contributeurs utilisent un fork selon [Contribution](../CONTRIBUTING.md) et [Validation](VALIDATION.md#2-validation-distante-du-bon-commit). Examiner les changements locaux et commencer avec un checkout propre, puis créer une branche adaptée au changement :

```bash
git remote -v
git status --short
git switch main
git pull --ff-only
git switch -c docs/mon-changement
```

Effectuer le changement, suivre les contrôles et la revue de l'index dans [Validation](VALIDATION.md#2-validation-distante-du-bon-commit), puis pousser la branche et ouvrir une PR. La protection de `main` impose ce parcours au mainteneur aussi. Attendre les deux jobs `checks` et `bootstrap-wsl` sur le bon commit et relire le diff.

Pour fusionner avec la CLI depuis cette branche, saisir le numéro de PR. L'identité locale doit déjà utiliser l'adresse noreply : l'option ci-dessous la transmet aussi pour le commit de fusion créé sur GitHub et exige le commit local exact. Une fusion via l'interface web utilise les [préférences d'adresse du compte GitHub](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address), à vérifier séparément.

```bash
read -r pr_number
gh pr merge "$pr_number" --merge \
  --author-email "$(git config --get user.email)" \
  --match-head-commit "$(git rev-parse HEAD)"
unset pr_number
```

Après fusion, avec un checkout propre :

```bash
git switch main
git pull --ff-only
git status --short
mise run workstation:config-audit --check
mise run workstation:doctor
```

Si la PR change des ressources à provisionner, examiner les différences locales avant d'appliquer `mise bootstrap --locked`, puis refaire les contrôles. Une nouvelle version d'outil peut demander `mise install --locked`. `git pull` récupère les sources ; il n'applique pas le provisionnement.

Pour remplacer un ancien bootstrap privé déjà installé, partir de l'historique neuf du public et conserver une archive privée vérifiée pour le retour arrière. Comparer les contenus versionnés et préserver le chemin du checkout, les fichiers locaux et les liens avant toute bascule. L'ancien historique reste dans l'archive privée : changer seulement l'URL d'un ancien clone conserverait ses commits privés. Valider le poste avant de supprimer l'ancien dépôt GitHub. Le dépôt de sauvegarde chiffrée, s'il est utilisé, reste distinct et privé.

## Versions et changements

Les commandes quotidiennes `updateall` et `devupdate` conservent leur fonctionnement : mise, outils, dépôts shell et Codex actif sont mis à jour. Elles peuvent changer les lockfiles ; examiner ces changements avant commit. Elles ne capturent aucune configuration et ne font aucun commit/push.

Pour actualiser uniquement les versions verrouillées, sans mise à jour des packages système ou du shell :

```bash
mise -E github,secrets lock --global --bump
mise -E github,secrets install --locked
mise run workstation:check
git diff --stat
git diff -- config.toml config.github.toml config.secrets.toml mise.lock mise.github.lock mise.secrets.lock
```

`--bump` réévalue les sélecteurs ; sans ce flag, `mise lock` conserve les versions déjà résolues. Examiner origines, URL de téléchargement, empreintes et attestations disponibles. Pour ajouter un outil sans changer les autres versions, utiliser `mise lock --global NOM_OUTIL`, puis `mise install NOM_OUTIL --locked`.

La version de mise utilisée par le nouvel installateur et par la CI vient uniquement de [system/bootstrap/mise.json](../system/bootstrap/mise.json). Pour la changer : télécharger le `install.sh` de la release officielle choisie, calculer son SHA-256, mettre à jour les deux champs du JSON et relire le script. Adapter `min_version` de `config.toml` seulement si les nouvelles fonctionnalités l'exigent. `python3 scripts/bootstrap_metadata.py` vérifie le format et la cohérence du minimum. Tester ensuite l'installation neuve en CI. Ne jamais remplacer l'empreinte seulement pour contourner un échec de téléchargement.

## Reproductibilite

`mise install --locked` reprend les CLI du lockfile. L'installation de mise est fixée par les métadonnées et vérifie le script téléchargé. Le socle shell suit normalement les branches amont ; [config.reproducible.toml](../config.reproducible.toml) fournit une alternative avec cinq commits explicites.

Pour une installation neuve depuis le snapshot, utiliser temporairement :

```bash
mise -E reproducible bootstrap --update --locked
```

Avec des capacités également temporaires, les énumérer ensemble, par exemple `mise -E reproducible,wsl,github bootstrap --update --locked`. Ne pas conserver `reproducible` dans le sélecteur : sa réapplication peut ramener les dépôts aux anciens commits. Sur un poste existant, cette option peut déplacer leurs références ; la réserver aux installations jetables ou à une reprise volontairement choisie.

Lors d'un futur `shell:update`, le helper rattache au préalable les clones propres et détachés qui correspondent exactement au snapshot et à leur origine, puis les commandes habituelles les actualisent. Les branches existantes ne changent pas. Les clones modifiés ou détachés à un autre commit sont laissés intacts et signalés. Examiner tout avertissement avant de poursuivre.

Après une mise à jour et une validation du shell, rafraîchir volontairement le snapshot :

```bash
mise run shell:freeze
mise run workstation:check
git diff -- config.reproducible.toml
```

`freeze` exige des dépôts propres et des origines conformes ; il n'effectue aucun téléchargement ni changement dans ces dépôts. Valider les nouveaux commits dans une installation WSL neuve avant de les livrer. APT, l'installateur Codex et les applications Windows restent évolutifs ; ce projet ne fournit pas une image système entièrement figée.

## Validation

Après l'installation générique, installer les outils de test pour une invocation temporaire, puis lancer le contrôle complet :

```bash
mise -E secrets install --locked
mise run workstation:check
mise run workstation:config-audit --check
mise run workstation:doctor --bootstrap
```

`workstation:check` enchaîne lint, scan Gitleaks de l'historique et des fichiers, puis `mise -E secrets run workstation:test`. Il s'arrête au premier échec. Les tests utilisent des répertoires temporaires et de vraies CLI age, fnox, Git et OpenSSH avec des données fictives. Ils n'installent pas de packages et ne restaurent rien dans le compte courant.

Les régressions couvrent la sélection des capacités, l'intégrité de l'installateur, les refus d'écrasement et de liens symboliques, le chiffrement et la restauration exacte des clés, l'identité Git effective, les destinataires age non autorisés, les configurations fnox actives, les erreurs d'écriture, la sauvegarde atomique du coffre, les codes du diagnostic et l'export depuis un commit avec son manifeste. Les mises à jour depuis un snapshot shell sont testées sur des clones Git jetables.

Le test KeePassXC crée, modifie, capture, restaure et rouvre un coffre sans écran ; un mauvais mot de passe doit échouer. Il est obligatoire si `vault` est actif, comme en CI WSL personnelle. Sans cette capacité et sans CLI, il est explicitement ignoré ; les autres tests cryptographiques restent exécutés.

La CI `Quality` s'exécute sur les PR, les push vers `main`, chaque lundi et à la demande. Elle annule les runs précédents du même groupe. Ses actions sont fixées à leurs SHA, ses permissions restent `contents: read`, et elle n'utilise aucun secret personnel.

1. Ubuntu 26.04 : lint, Gitleaks, tests ; export du commit, vérification du manifeste et des sources exportées ; archivage en conservant les modes exécutables.
2. Windows : import de cette archive, vérification du manifeste, création d'Ubuntu 26.04 WSL et du compte `contributor`, installation générique depuis le snapshot puis personnelle, second bootstrap sans dérive, shell interactif, services WSLInterop et coffre KeePassXC fonctionnel.

La CI ne valide pas les comptes réels, la MFA, Docker Desktop, l'interface graphique KeePassXC ni les sauvegardes hors ligne. La [Validation pas à pas](VALIDATION.md) relie le run au bon commit et sépare la contribution publique de la reprise personnelle facultative. Le diagnostic complet du poste vient après ses connexions natives : `mise run workstation:doctor`.

Pour un projet applicatif, une analyse supplémentaire est disponible : `mise run security:scan /chemin/du/projet`. Trivy examine les dépendances et configurations qu'il reconnaît, télécharge ses bases et renvoie 1 pour les alertes HIGH/CRITICAL. Ce contrôle ponctuel ne couvre pas tous les exécutables du poste. [Documentation Trivy](https://trivy.dev/docs/latest/target/filesystem/).

## Automatisation des dependances

[renovate.json](../renovate.json) prépare des PR de dépendances mise et GitHub Actions, sans fusion automatique, chaque lundi. Le motif explicite inclut les `config*.toml` à la racine, que le motif standard du [gestionnaire mise Renovate](https://docs.renovatebot.com/modules/manager/mise/) ne couvre pas dans cette arborescence.

La configuration seule n'active aucun bot. Dans le dépôt cible, installer/autoriser l'application Renovate sur ce dépôt, puis vérifier l'onboarding et le Dependency Dashboard. La mise à jour des lockfiles dépend aussi de la politique d'exécution du service Renovate ; si elle est refusée, utiliser le parcours manuel ci-dessus. La version et l'empreinte de l'installateur mise, les commits shell, APT et Codex restent à revoir explicitement. Examiner la CI et le diff de chaque PR avant fusion.

## Publication

L'ancien dépôt privé conserve son historique. Préparer un nouveau dépôt à partir d'un **commit relu et validé**, dans un répertoire neuf extérieur au checkout :

```bash
mise run publication:prepare --ref HEAD --output /tmp/workstation-public
mise run publication:check --output /tmp/workstation-public
```

Le premier script lit les blobs du commit, sans les modifications locales ni les fichiers nouveaux non commités. Il refuse les catégories inattendues, fichiers privés connus, liens symboliques et chemins de compte détectés ; il exécute Gitleaks et initialise un Git sans commit ni remote. L'empreinte SHA-256 et le mode de chaque fichier figurent dans `/tmp/workstation-public.manifest.json`, à conserver séparément pour la traçabilité. Le manifeste contient le SHA source privé ; il n'est pas destiné au dépôt public.

Pour une prévisualisation avant commit, choisir une autre destination :

```bash
mise run publication:prepare --working-tree --output /tmp/workstation-public-preview
mise run publication:check --output /tmp/workstation-public-preview
```

Cette prévisualisation inclut les fichiers suivis modifiés et les nouveaux non ignorés. Elle ne remplace pas la validation d'un commit final. Une option `--markers-file /chemin/prive/marqueurs.txt` permet d'ajouter des noms, e-mails et chemins à refuser, un par ligne, sans les afficher. Ce fichier doit rester hors du checkout. Aucun détecteur ne reconnaît toute donnée personnelle : relire **chaque fichier** exporté.

La vérification du manifeste doit précéder tout ajout, modification, commit ou remote dans l'export. Pour corriger un fichier, corriger la source, commiter et réexporter dans une destination neuve. La CI teste cet export dans une WSL neuve. Vérifier également que le poste personnel fonctionne encore ; si le bundle est utilisé, effectuer sa reprise réelle selon [Validation](VALIDATION.md#3-premiere-sauvegarde-personnelle).

Seulement au moment choisi pour publier, configurer une identité Git locale *noreply* et une signature distincte, relire l'index puis créer le premier commit de l'export. Créer un **nouveau** dépôt public et y pousser ; ne jamais rendre public le dépôt privé d'origine. Sur GitHub, activer les signalements privés de vulnérabilité, protéger `main` avec les deux contrôles `checks` et `bootstrap-wsl`, limiter les droits d'écriture et vérifier les Actions. Renovate reste facultatif. Ces réglages dépendent du dépôt cible et ne sont pas créés par les scripts.

Licence [MIT](../LICENSE) ; les dépendances gardent leurs propres licences. Voir [Contribution](../CONTRIBUTING.md) et [Sécurité](../SECURITY.md).

## Retour arriere et incidents

Revenir à un commit de configuration connu et réinstaller les versions verrouillées. Cela ne restaure pas automatiquement les anciennes versions APT, mise, Codex ou Windows. Désactiver une capacité ne retire ni packages ni services ; examiner les ressources avant toute suppression explicite.

Sur un poste déjà configuré, préserver les fichiers locaux d'identité, signature, SSH, préférences et capacités. Les sauvegardes éventuelles sous `~/.local/state/workstation/migration` sont privées et ne doivent pas être publiées. Une alerte réelle de secret implique révocation/rotation et analyse de l'historique. Une exception de scanner doit rester ciblée sur un faux positif établi.
