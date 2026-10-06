# Architecture

[README](../README.md) · [Operations](OPERATIONS.md) · [Tools](TOOLS.md) · [Maintenance](MAINTENANCE.md)

## Responsabilites

Le dépôt s'installe dans `~/.config/mise` et fournit la configuration globale mise. `config.toml` est le socle générique. Les fichiers `config.<capacité>.toml` ajoutent leurs outils, packages, services et indicateurs de capacité. `miserc.toml`, ignoré par Git, choisit les environnements actifs. `config.local.toml`, également ignoré, permet des valeurs propres au poste telles que `WORKSTATION_SSH_KEY`.

| Domaine | Source de vérité |
| --- | --- |
| CLI et versions | mise et `mise*.lock` |
| Installateur mise et minimum | `system/bootstrap/mise.json` et `min_version` |
| Snapshot shell facultatif | `config.reproducible.toml`, environnement temporaire |
| Packages Ubuntu, fichiers système, services | Bootstrap mise et APT |
| Shell et configuration Git commune | Dotfiles versionnés, liés par mise |
| Sélection de capacités | Sélecteur local mise |
| Identité Git et signature | `~/.config/git/identity.conf` et `allowed_signers` locaux |
| SSH privé | Fichier local protégé ; agent géré par Keychain |
| Secrets restaurables | Valeurs fnox chiffrées par age dans un dépôt privé |
| Mots de passe humains | Coffre KeePassXC chiffré, déverrouillé manuellement |
| Sessions GitHub, Google Cloud, Codex | Connexions natives sur chaque installation |
| Docker Desktop, VS Code | Hôte Windows |

Les profils `generic` et `personal` ne sélectionnent pas le snapshot `reproducible`. Cette variante temporaire ajoute uniquement des références de dépôts, sans outils ni données personnelles. Les versions APT, Codex et Windows restent indépendantes.

Le [suivi des configurations](CONFIGURATION.md) explicite les fichiers liés, les copies système et les préférences locales hors du bundle. `workstation:config-audit` compare les ressources déclarées pour les capacités actives ; il n'importe et ne sauvegarde aucun fichier. Les exemples de configuration restent facultatifs et ne sont pas déployés.

Chaque capacité émet un indicateur `WORKSTATION_<NOM>` utilisé par le bootstrap final, les tâches, le shell et le diagnostic. Le socle remet tous les indicateurs à zéro : désactiver une capacité ne dépend pas de la présence résiduelle d'un binaire. Les tâches Codex et Docker refusent de s'exécuter quand leur capacité est inactive.

## Cycle du bootstrap

`mise bootstrap --update --locked` applique les ressources déclaratives, les dotfiles, le shell de connexion, les outils verrouillés puis la tâche `bootstrap`. Le profil cloud ajoute sa clé publique et son dépôt APT en phase `pre-packages`. `--update` rafraîchit ensuite les index nécessaires à `google-cloud-cli`.

La capacité WSL conserve `WORKSTATION_WSL=1`. WSL gère nativement l'interop Windows ; le doctor vérifie l'exécution de CMD depuis `/mnt/c`. La seule adaptation système est le drop-in déclaratif `ConditionVirtualization=!wsl` : le registre binfmt est protégé par WSL, et `systemd-binfmt` doit rester inactive/skipped sur cette plateforme. Il prend effet au prochain démarrage WSL.

## Donnees privees

Le dépôt public contient seulement le code des parcours et leurs exemples. Le bundle privé contient `bundle.json` (version de format), `fnox.toml` et éventuellement `vault.kdbx`. L'identité Git utilisateur effective est elle aussi chiffrée dans fnox ; la lecture se fait hors de tout dépôt pour exclure une surcharge locale. Aucun chemin absolu du poste d'origine n'est restauré : les destinations sont calculées pour le nouvel utilisateur.

La configuration fnox du bundle est volontairement limitée au fournisseur age, au destinataire public de la clé dédiée et à trois entrées : `IDENTITY`, `SSH_PRIVATE_KEY`, `SSH_PUBLIC_KEY`. Tout destinataire supplémentaire est refusé. Les imports, commandes de fournisseur, valeurs par défaut en clair et clés de déchiffrement dans la configuration sont refusés. `env = false` évite d'injecter les secrets dans le shell. Les invocations fnox utilisent une copie privée des octets validés, isolée de sa configuration globale et de ses variables héritées.

La capture encode les fichiers avant chiffrement et la restauration décode les résultats sans altérer leurs octets. Elle contrôle la paire SSH, prépare les écritures avec des permissions privées et refuse les destinations existantes ou symboliques. Le contenu déchiffré peut exister brièvement dans un répertoire temporaire privé pour OpenSSH et Git ; il n'est ni journalisé ni versionné. Une coupure brutale peut laisser ces fichiers temporaires : protéger aussi le stockage du poste et son compte utilisateur.

La clé age et le mot de passe maître KeePassXC sont indépendants. Une copie du bundle seule ne doit pas permettre son déchiffrement. La mise à jour du KDBX sauvegarde le snapshot précédent hors du bundle, puis effectue un remplacement atomique ; elle ne déverrouille jamais le coffre. Les comptes OAuth, caches de session, données des navigateurs, mots de passe système, clés GPG et secrets propres aux projets ne sont pas capturés par ces tâches.

## Portabilite et limites

La cible prise en charge est Ubuntu 26.04 WSL2 sur x86-64. Une autre distribution ou architecture nécessite une validation de ses packages, des binaires et des intégrations. La CLI KeePassXC fonctionne sans interface graphique ; son interface nécessite WSLg ou une installation adaptée sur l'hôte.

Les chemins personnels, noms de compte, adresse Git, signature et dépôt privé sont des données locales. Google Cloud, GitHub, Codex et Docker Desktop sont des capacités facultatives. La CI utilise le compte `contributor` pour détecter les dépendances accidentelles à un compte personnel.

## References

- [Environnements mise](https://mise.jdx.dev/configuration/environments.html)
- [Secrets mise](https://mise.jdx.dev/environments/secrets/) : fnox recommandé ; intégrations SOPS et age direct expérimentales.
- [Intégration fnox/mise](https://fnox.jdx.dev/guide/mise-integration.html)
- [Configuration fnox](https://fnox.jdx.dev/reference/configuration)
- [Guide KeePassXC](https://keepassxc.org/docs/KeePassXC_UserGuide)
