# Contribuer

La cible est Ubuntu 26.04 WSL2 x86-64. Commencer avec l'installation générique du [README](README.md) dans une distro jetable. Aucune identité ou connexion de l'auteur n'est nécessaire.

Les capacités facultatives sont activées avec `mise run profile:select`. Ne pas commiter `miserc.toml`, `config.local.toml`, une identité Git personnelle, des secrets ou des fichiers de récupération. Utiliser une adresse GitHub noreply pour les contributions publiques si nécessaire.

Utiliser la documentation comme parcours de validation. Toute commande nécessaire qui diffère du runbook doit entraîner sa correction dans la même contribution, puis une nouvelle validation du parcours documenté.

Avant une proposition :

```bash
mise -E secrets install --locked
mise run workstation:check
```

Pour un changement de provisionnement, tester également un bootstrap neuf puis un second passage sans dérive. Décrire ce qui a été vérifié et ce qui reste manuel. Actualiser les documents affectés. Employer des Conventional Commits, par exemple `feat: add optional capability` ou `fix: preserve recovery file permissions`.

Signaler une vulnérabilité selon [SECURITY](SECURITY.md). Ne jamais inclure de véritable clé ou jeton pour reproduire un problème.

Le code Python utilise seulement la bibliothèque standard de Python 3.11 ou plus récent. `ruff check --no-cache scripts tests` analyse le code ; `ruff format --no-cache scripts tests` le formate. Pour Bash, utiliser `shfmt -w -i 4 -ln bash chemin/du/script`. Les outils viennent de mise ; lancer ces commandes dans le shell configuré ou avec `mise exec --`.

Le [parcours de validation](docs/VALIDATION.md#2-validation-distante-du-bon-commit) explique comment relier une PR au run du bon commit, sur un fork comme sur le dépôt principal. Ne jamais utiliser de données réelles dans les fixtures.
