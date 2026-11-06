# Hermes depuis workstation

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Maintenance](MAINTENANCE.md)

Workstation installe une distribution vérifiée d'Hermes Runner Linux dans une
destination choisie et conserve configuration et données séparément. Hermes
possède le Kanban et l'orchestration ; Codex exécute les travaux ; Engineering SDD
garde la méthode et ses approbations. Seul le runner `codex-linux` est disponible.

La capacité `hermes` est facultative et exclue de `personal`. Elle ne nécessite
ni Windows, ni WSL, ni Docker Desktop. Linux x86-64, Bubblewrap et namespaces,
Git, Make, ripgrep et Docker Engine/Compose doivent être disponibles. Le bootstrap
Ubuntu peut provisionner les packages déclarés ; les tâches `hermes:*` ne lancent
jamais sudo ou APT. Les essais sous WSL2 ne qualifient pas Ubuntu physique.

## Provisionnement explicite

Les dépendances utilisateur sont Python 3.14.4, Codex 0.166.0 et gh 2.101.0,
déclarées dans l'environnement interne `config.hermes-tools.toml`, avec URLs et
hashes dans `mise.hermes-tools.lock`. La capacité `hermes` n'ajoute aucun de ces
binaires au PATH du shell : les tâches résolvent les versions exactes et les
exposent uniquement à leurs processus enfants. Le standalone Codex et les autres
capacités restent utilisables ensemble, indépendamment de l'ordre de sélection.
Ne pas enregistrer `hermes-tools` comme capacité personnelle.

La distribution est publiée dans la [release privée `v0.2.0`](https://github.com/m4rise/hermes-runner-linux/releases/tag/v0.2.0)
du dépôt `m4rise/hermes-runner-linux`, avec archive, SHA256 et manifeste.
L'acquisition exige une authentification gh autorisée à lire ce dépôt privé.
`hermes:fetch` télécharge cet asset via gh et vérifie le digest versionné dans
`system/hermes/release.json` avant de conserver le fichier. Aucun `latest` ni
branche flottante n'est utilisé. Un chemin absolu du poste de qualification ne
constitue pas une source pour une installation neuve. Une archive obtenue par
un autre canal peut toujours être fournie explicitement à `install`, avec le
même contrôle de digest. Hermes amont, pip et dépendances Python sont installés
par le composant avec leurs propres pins/hashes.

Depuis le checkout workstation, employer temporairement `-E hermes`. Cette
sélection ne réécrit pas `miserc.toml`. Les variables suivantes sont des exemples
de destinations à choisir ; le fichier d'authentification est lu côté autorité,
jamais copié par ces tâches dans le projet ou dans les workers.

```bash
hermes_root="$HOME/.local/share/hermes-runner"
hermes_release="$hermes_root/releases/0.2.0"
hermes_config="$HOME/.config/hermes-runner/sulu.json"
hermes_data="$HOME/.local/state/hermes-runner/sulu"
hermes_plugins="$hermes_root/plugins/engineering-sdd-0.4.0"
hermes_repository="m4rise/hermes-runner-linux"
hermes_archive="$HOME/.cache/hermes-runner/hermes-runner-linux-0.2.0.tar.gz"
read -r sulu_repository  # Checkout Sulu source, conservé en lecture seule
read -r github_repository  # OWNER/REPOSITORY

mise -E hermes run hermes:dependencies
mise -E hermes run hermes:fetch -- \
  --repository "$hermes_repository" --destination "$hermes_archive"
mise -E hermes run hermes:install -- \
  --archive "$hermes_archive" --destination "$hermes_release"
mise -E hermes run hermes:sdd-install -- \
  --installation "$hermes_release" --home "$hermes_plugins"
mise -E hermes run hermes:configure -- \
  --installation "$hermes_release" --config "$hermes_config" \
  --data "$hermes_data" --repository "$sulu_repository" \
  --github-repository "$github_repository" \
  --codex-auth "$HOME/.codex/auth.json" --sdd-home "$hermes_plugins" \
  --runner codex-linux --model gpt-6-astra --effort high \
  --compose-prefix cms-ci-hermes-user
mise -E hermes run hermes:run -- --config "$hermes_config" init
mise -E hermes run hermes:run -- --config "$hermes_config" doctor
```

`install` répété vérifie l'identité et l'intégrité du composant sans reconstruire
l'environnement ni toucher à l'état. Un répertoire existant non reconnu ou
divergent est refusé. `configure` refuse les fichiers/données existants ; répéter
`init` pour vérifier une configuration déjà initialisée. Les credentials GitHub
et Codex doivent être valides ; leur connexion/renouvellement reste manuel.

`sdd-install` appelle l'installation native Codex dans un home neuf ; il refuse
un home existant. Pour une installation conforme déjà choisie, passer simplement
son home à `configure --sdd-home`. `init` et `doctor` vérifient source/ref, pin,
ensemble exact des fichiers et découverte native. Aucun skill n'est recopié dans
les instructions. L'activation personnelle de la capacité par `profile:select`
reste un choix de l'utilisateur, avec toutes ses autres capacités à conserver.

## Confier un travail et consulter le resultat

La configuration créée par défaut autorise l'observation et les validations.
Pour une mission de développement, créer une configuration et un store neufs
avec `--autonomy development-isolated` et répéter `--allow-path CHEMIN` pour chaque
fichier autorisé. Les chemins sont relatifs au projet et exacts. Le runner garde
le checkout principal en lecture seule et conserve le travail développé pour
revue. Une autorisation d'édition n'autorise ni commit, ni push, ni PR ou merge.

Dans deux terminaux utilisant la même configuration :

```bash
mise -E hermes run hermes:run -- --config "$hermes_config" start
# Second terminal : titre et fichier d'objectif en langage naturel.
mise -E hermes run hermes:run -- --config "$hermes_config" \
  hermes kanban create 'Ma mission Sulu' --body-file ./mission.txt
mise -E hermes run hermes:run -- --config "$hermes_config" list
mise -E hermes run hermes:run -- --config "$hermes_config" result
```

`start` attend une mission puis traite un parcours borné et quitte. La commande
native `hermes kanban dispatch` n'est pas le lanceur de ce runner. Les limites
de requêtes, durée et cartes restent dans le JSON du composant ; leur modification
après initialisation n'est pas adoptée silencieusement.

Le résultat donne les handoffs, validations, revue distincte, diff et checkout
conservé. Lire ces preuves avant de décider. Une carte `done` ne vaut aucune
approbation SDD. Une demande pending expose décision, contexte, options et action
bloquée ; il n'existe pas d'approbation automatique ni de publication par le
wrapper workstation. Les opérations Git/GitHub approuvées se poursuivent sous les
instructions du projet, hors de cette capacité d'édition.

`WORKSTATION_HERMES_CONFIG` peut désigner un JSON choisi dans le `config.local.toml`
ignoré ; l'option `--config` garde priorité. Ce réglage ne lance aucune mission.

## Mise a jour sauvegarde et reprise

Demander l'arrêt, attendre la sortie du service, puis inspecter :

```bash
mise -E hermes run hermes:run -- --config "$hermes_config" stop --reason 'Pause utilisateur'
mise -E hermes run hermes:run -- --config "$hermes_config" diagnose
# Après inspection, annuler les opérations inachevées ; aucune relance aveugle.
mise -E hermes run hermes:run -- --config "$hermes_config" \
  reconcile --reason 'État et ressources examinés'
```

Les données et modifications sont conservées. La réconciliation n'est pas une
reprise automatique du thread : elle clôt les opérations incertaines. Soumettre
une nouvelle mission avec les preuves et le travail conservé seulement après
avoir examiné l'état. SIGKILL, panne machine et interventions concurrentes restent
des qualifications distinctes.

Service arrêté et état réconcilié :

```bash
mise -E hermes run hermes:backup -- --config "$hermes_config" \
  --destination "$HOME/hermes-backup.tar.gz"
mise -E hermes run hermes:restore -- --backup "$HOME/hermes-backup.tar.gz" \
  --destination "$HOME/hermes-restore-review"
```

L'archive privée contient configuration, stores et preuves ; elle n'est pas
chiffrée automatiquement. Le composant utilise SQLite backup pour ses bases.
La restauration exige une destination neuve, conserve les liens internes sûrs,
refuse les liens externes et extrait en quarantaine. Elle ne crée aucune
configuration active : `source-config.review.json` et
`RESTORE-REVIEW-REQUIRED.json` demandent de comparer révocations, ledger et skills
avec les décisions postérieures. L'activation d'un état restauré reste manuelle,
après cette revue ; aucun apprentissage révoqué n'est réactivé silencieusement.

Une nouvelle release exige son manifest et ses locks revus. `hermes:update`
prend les mêmes arguments qu'`install`, avec une destination neuve. Il ne bascule
aucune configuration. Qualifier d'abord un store neuf ; ensuite le composant
permet `adopt-config --previous ANCIEN_JSON --reason RAISON` pour les seuls
changements de chemins de dépendances au même contrat. Garder les deux JSON dans
le même répertoire et l'ancienne release pour un retour explicite par la même
commande. Une évolution de schéma/projet/gouvernance n'a pas de migration automatique.

```bash
mise -E hermes run hermes:uninstall -- \
  --installation "$hermes_release" --config "$hermes_config"
```

La désinstallation délègue au contrôle du composant : service arrêté, absence
d'état incertain et données/configuration hors installation. Elle retire la
release choisie, préserve données, plugins, credentials et backups. Vérifier les
autres configurations qui pourraient utiliser la même release avant suppression.

## Validation dans un environnement isole

Pour tester un worktree workstation sans activer le profil personnel, choisir
un répertoire expérimental neuf et utiliser les variables mise natives :

```bash
read -r workstation_checkout
read -r hermes_trial
export MISE_CONFIG_DIR="$workstation_checkout"
export MISE_GLOBAL_CONFIG_ROOT="$workstation_checkout"
export MISE_DATA_DIR="$hermes_trial/mise-data"
export MISE_CACHE_DIR="$hermes_trial/mise-cache"
export MISE_STATE_DIR="$hermes_trial/mise-state"
export MISE_ENV=hermes
export MISE_TRUSTED_CONFIG_PATHS="$workstation_checkout"
export MISE_TASK_DISABLE_PATHS="$HOME/.config/mise/tasks"
export MISE_TASK_RUN_AUTO_INSTALL=false
cd "$workstation_checkout"
mise tasks ls  # Vérifier que les tâches hermes viennent de ce checkout.
```

Appliquer ensuite les tâches précédentes avec installation, plugin, configuration
et données sous `hermes_trial`. Les tâches de provisionnement ne changent pas les
dotfiles ni la configuration système. `MISE_TASK_DISABLE_PATHS` évite que les
tâches globales homonymes masquent celles du worktree. Ne pas lancer le bootstrap
global pour cette qualification. Tests de contrat locaux :

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_hermes.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_profiles.py -v
```

Ces tests prouvent refus d'intégrité, idempotence, préservation et confinement de
restauration avec fixtures. Ils ne prouvent pas l'inférence, le développement Sulu
ou Ubuntu physique ; le rapport de la distribution conserve ces résultats réels.
