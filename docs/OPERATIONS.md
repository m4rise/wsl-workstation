# Operations

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Tools](TOOLS.md) · [Maintenance](MAINTENANCE.md)

## Capacites et controles

```bash
devprofile personal
mise bootstrap --update --locked
exec zsh -l
devdoctor
```

Sur une installation sans alias, utiliser les commandes `mise run` indiquées dans le README. `devprofile generic` revient au socle ; `devprofile wsl github` choisit une liste précise. Cela ne désinstalle rien. `mise config ls` permet de voir les fichiers réellement chargés.

```bash
mise -E secrets install --locked
devcheck
devconfig --check
devversions
devdoctor --bootstrap
```

Le lint vérifie les sources Bash, la syntaxe Zsh, la qualité et le formatage Python avec Ruff, les métadonnées, les exemples et les configurations TOML, les workflows et les liens Markdown locaux avec leurs ancres. L'audit Gitleaks couvre l'historique Git complet et les fichiers présents, avec masquage. Le diagnostic `--bootstrap` ne valide aucune authentification ; le diagnostic normal contrôle les intégrations sélectionnées.

## Identite Git et SSH

Les préférences Git communes, dont `rerere`, viennent des dotfiles versionnés. Les préférences ajoutées dans `~/.gitconfig` et les règles de `~/.ssh/config` restent locales et ne sont pas intégralement capturées. Voir [le suivi des configurations](CONFIGURATION.md) avant de les intégrer ou de réappliquer le bootstrap.

Le fichier commun inclut `~/.config/git/identity.conf`. Ce fichier est propre au poste, extérieur au dépôt. Créer une identité sans inscrire ses valeurs dans l'historique du shell :

```bash
install -d -m 700 "$HOME/.config/git"
umask 077
read -r git_name
read -r git_email
git config --file "$HOME/.config/git/identity.conf" user.name "$git_name"
git config --file "$HOME/.config/git/identity.conf" user.email "$git_email"
unset git_name git_email
```

Pour une nouvelle clé, vérifier d'abord que la destination est libre, puis laisser OpenSSH demander une phrase secrète :

```bash
test ! -e "$HOME/.ssh/id_ed25519"
install -d -m 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519"
```

`sshunlock` utilise `WORKSTATION_SSH_KEY`, qui vaut par défaut `~/.ssh/id_ed25519`. Pour conserver un autre nom, le définir dans `[env]` de `config.local.toml`. Le choix local existant est préservé lors de la migration.

Avec la capacité GitHub active, se connecter puis ajouter la clé publique :

```bash
sshunlock
gh auth login --hostname github.com --web --git-protocol https
gh ssh-key add "$HOME/.ssh/id_ed25519.pub" --type authentication --title "Workstation WSL"
ssh -T git@github.com
```

GitHub renvoie normalement le code 1 après une authentification SSH réussie, car aucun shell distant n'est fourni. Vérifier son message.

La signature est facultative. Pour une clé SSH déjà enregistrée comme clé de signature sur GitHub :

```bash
git config --file "$HOME/.config/git/identity.conf" gpg.format ssh
git config --file "$HOME/.config/git/identity.conf" user.signingkey "$HOME/.ssh/id_ed25519.pub"
git config --file "$HOME/.config/git/identity.conf" commit.gpgsign true
git config --file "$HOME/.config/git/identity.conf" tag.gpgSign true
```

Pour les contributions publiques, utiliser l'adresse *noreply* fournie dans les paramètres GitHub. Depuis le clone public, saisir le pseudo public puis cette adresse, une entrée par ligne, et configurer uniquement ce dépôt :

```bash
read -r public_name
read -r public_email
git config --local user.name "$public_name"
git config --local user.email "$public_email"
unset public_name public_email
```

Une clé dédiée à la signature est recommandée ; une clé SSH existante peut aussi signer si sa partie publique est enregistrée comme **Signing Key** sur GitHub. L'ajout se fait dans les paramètres SSH and GPG keys du compte, ou avec `gh ssh-key add CHEMIN_CLE_PUBLIQUE --type signing` si la CLI dispose du droit correspondant. Voir [la procédure GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account).

Pour activer la signature uniquement dans ce clone, saisir le chemin absolu de la clé publique choisie, puis exécuter :

```bash
read -r signing_public_key
test -f "$signing_public_key"
git config --local gpg.format ssh
git config --local user.signingkey "$signing_public_key"
git config --local commit.gpgsign true
git config --local tag.gpgSign true
unset signing_public_key
```

Charger la clé correspondante dans l'agent SSH depuis son terminal pour signer sans saisir la phrase secrète dans un autre outil. Ces commandes locales conservent l'identité globale des autres projets ; un `includeIf` Git local peut également servir à plusieurs clones publics. Ne pas réutiliser automatiquement ton adresse privée pour le premier commit public.

## Bundle prive

Le bundle est facultatif. Les commandes qui suivent sont à exécuter dans ton terminal : les vraies clés, le mot de passe maître et les phrases secrètes ne doivent pas être transmis à un assistant ni copiés dans un ticket.

### Premiere capture

Activer les outils et créer une clé age dédiée, hors de tout dépôt :

```bash
mise run profile:select github cloud codex docker wsl secrets vault
mise bootstrap --update --locked
mise run secrets:init --age-key "$HOME/.config/fnox/age.txt"
```

Cette commande initialise `~/.local/share/workstation-private`, mais ne publie rien. Si la clé age n'existe pas, elle est générée avec des permissions privées. Faire **deux sauvegardes hors ligne** de cette clé, séparées du bundle. Si elle est perdue et qu'aucune copie n'existe, les données chiffrées sont irrécupérables.

La clé locale est un fichier en clair protégé par les permissions Linux. Une clé conservée sur le poste n'est pas une clé exclusivement hors ligne : pour ce fonctionnement, ne l'y rendre disponible que pendant la capture ou la reprise, puis conserver les copies sur les supports hors ligne. Les tâches acceptent leur chemin avec `--age-key`. Ne pas supprimer la dernière copie utilisable avant d'avoir testé les deux sauvegardes.

Si aucun support hors ligne n'est immédiatement disponible, utiliser seulement comme solution transitoire deux stockages indépendants et chiffrer la clé côté client avec une phrase de récupération distincte conservée sur papier. Une copie cloud ne doit jamais recevoir `age.txt` en clair :

```bash
age --passphrase --output "/stockage-1/age-identity.txt.age" "$HOME/.config/fnox/age.txt"
if age --decrypt "/stockage-1/age-identity.txt.age" |
  cmp -s - "$HOME/.config/fnox/age.txt"; then
  echo "Sauvegarde vérifiée"
else
  echo "ÉCHEC : sauvegarde inutilisable"
fi
```

Copier ensuite seulement le fichier `.age` vers le second stockage et comparer leurs empreintes SHA-256. La phrase de cette enveloppe ne doit être ni celle du coffre KeePassXC, ni stockée dans ce coffre ou dans fnox. Des stockages connectés restent exposés à une suppression ou un rançongiciel communs : créer une véritable copie hors ligne dès que possible.

La capture lit l'identité Git utilisateur effective depuis un emplacement hors de tout dépôt. Une identité configurée seulement dans le dépôt courant ne peut donc pas remplacer celle à sauvegarder. Elle sauvegarde seulement les fichiers explicitement indiqués :

```bash
mise run secrets:capture \
  --age-key "$HOME/.config/fnox/age.txt" \
  --ssh-key "${WORKSTATION_SSH_KEY:-$HOME/.ssh/id_ed25519}" \
  --vault-file "$HOME/.local/share/keepassxc/vault.kdbx"
mise run secrets:check --age-key "$HOME/.config/fnox/age.txt"
```

Adapter le chemin de clé à ton fichier existant. Omettre `--ssh-key` ou `--vault-file` pour ne pas inclure ces données. Une clé SSH protégée conserve sa phrase secrète ; OpenSSH la demande pour vérifier la paire. Une nouvelle capture renouvelle l'identité et les entrées SSH fournies ; elle conserve les anciennes entrées SSH si l'option est omise. Retirer explicitement ces deux entrées chiffrées du bundle pour abandonner leur sauvegarde.

`secrets:check` ne restaure rien : il vérifie le destinataire age, le déchiffrement et la correspondance des clés SSH présentes. OpenSSH peut demander leur phrase secrète. Pour un coffre, il contrôle seulement l'en-tête KDBX ; sa véritable ouverture reste à valider avec KeePassXC. Les écritures incomplètes sont supprimées lors d'une erreur normale ; une interruption brutale exige de vérifier les fichiers laissés sur place avant de recommencer.

KeePassXC crée ou ouvre un coffre `.kdbx` avec son propre mot de passe maître. Conserver ses réglages de chiffrement recommandés et un mot de passe maître long. Ne pas le stocker dans fnox. La première capture accepte un coffre seulement lorsque le bundle n'en contient pas encore.

Après toute modification du coffre local, mettre à jour sa copie dans le bundle avec la commande dédiée :

```bash
mise run secrets:vault-update \
  --age-key "$HOME/.config/fnox/age.txt" \
  --vault-file "$HOME/.local/share/keepassxc/vault.kdbx"
```

La tâche exige les capacités `secrets` et `vault`. Elle vérifie le format KDBX sans demander le mot de passe maître, vérifie que la clé age correspond au destinataire unique du bundle, sauvegarde l'ancien snapshot sous `~/.local/state/workstation/vault-backups`, puis remplace `vault.kdbx` atomiquement. Des octets identiques ne créent ni remplacement ni nouvelle sauvegarde. `--backup-dir` permet de choisir un autre répertoire privé situé hors des dépôts public et privé.

La vérification d'en-tête ne prouve pas que le mot de passe maître ouvre le coffre. Contrôler la copie effectivement placée dans le bundle, puis publier le nouveau snapshot :

```bash
bundle="$HOME/.local/share/workstation-private"
mise run secrets:check --age-key "$HOME/.config/fnox/age.txt"
env -u DISPLAY -u WAYLAND_DISPLAY keepassxc-cli db-info "$bundle/vault.kdbx"
gitleaks dir --redact "$bundle"
git -C "$bundle" add vault.kdbx
git -C "$bundle" diff --cached --check
git -C "$bundle" diff --cached --stat
git -C "$bundle" commit -m "chore: update recovery vault"
git -C "$bundle" push
```

Créer ensuite une nouvelle archive chiffrée portant un nouveau nom :

```bash
bundle="$HOME/.local/share/workstation-private"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="/stockage-1/workstation-private-$stamp.tar.gz.age"
test ! -e "$archive"
tar --exclude=.git -C "$bundle" -czf - . |
  age --passphrase --output "$archive"
age --decrypt "$archive" | tar -tzf - >/dev/null &&
  echo "Archive du bundle mise à jour et vérifiée"
sha256sum "$archive"
unset stamp archive
```

Copier l'archive vers le second stockage, attendre sa synchronisation et comparer leurs empreintes. Garder l'ancienne archive et le backup local jusqu'à cette validation ; leur suppression ultérieure reste une décision explicite.

Créer un dépôt privé si nécessaire, puis publier uniquement les fichiers prévus :

```bash
read -r private_repo  # OWNER/REPOSITORY privé
# À exécuter seulement si le dépôt distant n'existe pas encore :
gh repo create "$private_repo" --private

bundle="$HOME/.local/share/workstation-private"
gitleaks dir --redact "$bundle"
git -C "$bundle" add .gitignore README.md bundle.json fnox.toml
if [[ -f "$bundle/vault.kdbx" ]]; then
  git -C "$bundle" add vault.kdbx
fi
git -C "$bundle" diff --cached --stat
git -C "$bundle" commit -m "feat: add encrypted recovery bundle"
git -C "$bundle" remote add origin "https://github.com/$private_repo.git"
gh auth setup-git
git -C "$bundle" push -u origin main
```

Ne pas ajouter la clé age, une exportation CSV/XML du coffre, des fichiers `.env` ou des caches de connexion. Le bundle privé ne doit contenir que ses métadonnées et des données chiffrées. Pour le coffre binaire, éviter les modifications simultanées sur plusieurs postes ; résoudre un conflit avec les fonctions de fusion KeePassXC, jamais avec une fusion textuelle Git.

Créer aussi une copie du snapshot indépendante de GitHub. Si aucun support hors ligne n'est disponible, chiffrer cette archive côté client avant de la placer sur les deux stockages transitoires. La phrase de l'enveloppe de récupération déjà conservée sur papier peut être réutilisée pour ces artefacts liés :

```bash
bundle="$HOME/.local/share/workstation-private"
archive="/stockage-1/workstation-private.tar.gz.age"
test ! -e "$archive"
tar --exclude=.git -C "$bundle" -czf - . |
  age --passphrase --output "$archive"
age --decrypt "$archive" | tar -tzf - >/dev/null &&
  echo "Archive du bundle vérifiée"
```

Copier seulement l'archive `.age` vers le second stockage, attendre sa synchronisation et comparer les empreintes SHA-256. Cette copie contient le snapshot courant sans historique Git ; le dépôt privé reste la source des versions précédentes. Créer une copie réellement hors ligne dès qu'un support adapté est disponible.

### Reprise sur une WSL neuve

Après l'installation générique du README :

```bash
mise run profile:select personal
mise bootstrap --update --locked
# Connexion au dépôt privé par HTTPS : aucune clé SSH restaurée n'est nécessaire.
gh auth login --hostname github.com --web --git-protocol https
gh auth status --hostname github.com
```

Si la clé capturée doit conserver un chemin non standard, le déclarer avant la restauration dans la configuration locale ignorée par Git. Exemple pour `~/.ssh/github` :

```bash
cd "$HOME/.config/mise"
cat >config.local.toml <<'EOF'
[env]
WORKSTATION_SSH_KEY = "{{ env.HOME }}/.ssh/github"
EOF
chmod 600 config.local.toml
```

Une sauvegarde age placée sur un disque Windows doit être déchiffrée vers le système de fichiers Linux, où ses permissions peuvent être imposées. Adapter le chemin source :

```bash
encrypted_age_key="/mnt/d/Workstation-Recovery/age-identity.txt.age"
restored_age_key="$HOME/.config/fnox/age.txt"
test -f "$encrypted_age_key"
test ! -e "$restored_age_key"
install -d -m 700 "$HOME/.config/fnox"
(
  umask 077
  age --decrypt --output "$restored_age_key" "$encrypted_age_key"
)
chmod 600 "$restored_age_key"
age-keygen -y "$restored_age_key" >/dev/null
stat -c '%a %U:%G %n' "$HOME/.config/fnox" "$restored_age_key"
unset encrypted_age_key restored_age_key
```

Restaurer enfin les éléments explicitement choisis :

```bash
read -r private_repo
mise run secrets:restore \
  --repo "$private_repo" \
  --age-key "$HOME/.config/fnox/age.txt" \
  --ssh --vault
exec zsh -l
sshunlock
```

Le fichier age doit appartenir à ton compte Linux avec mode `0600` ou `0400`. Si le support Windows ne préserve pas ces permissions, copier temporairement la clé dans un répertoire Linux privé, puis utiliser ce chemin. Conserver ses sauvegardes hors ligne.

Le démarrage du nouveau shell charge Keychain. Si la clé restaurée est protégée, `exec zsh -l` peut donc demander sa phrase secrète avant même l'appel explicite à `sshunlock`. Ce second appel est sans danger et confirme que la clé est disponible dans l'agent.

Lors du premier `ssh -T git@github.com`, OpenSSH peut demander de confirmer la clé hôte. Comparer l'empreinte affichée avec la [documentation officielle de GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/testing-your-ssh-connection) avant de répondre `yes`. Pour ED25519, l'empreinte attendue est `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`. Ne jamais accepter une empreinte différente sans investigation.

`--ssh` et `--vault` sont des choix explicites. Sans eux, seule l'identité est restaurée. Les destinations sont `~/.config/git/identity.conf`, `~/.ssh/id_ed25519` (ou le chemin local configuré), les fichiers publics associés et `~/.local/share/keepassxc/vault.kdbx`. Si une destination existe, la tâche échoue avant d'écrire ; la déplacer volontairement vers une sauvegarde privée avant de réessayer. Elle n'écrase pas un poste déjà configuré.

Pour une copie hors ligne ou un dépôt déjà cloné :

```bash
mise run secrets:restore \
  --bundle "/chemin/vers/bundle-prive" \
  --age-key "/chemin/separe/age.txt" \
  --ssh --vault
```

Le bundle est validé avant fnox : les configurations exécutables, imports, valeurs en clair et liens symboliques sont refusés. La restauration vérifie la paire SSH. Elle conserve un coffre chiffré ; ouvrir ensuite celui-ci avec KeePassXC et son mot de passe maître pour valider son accès réel.

### KeePassXC sans interface

La CLI fonctionne sans `DISPLAY`, sans Wayland et sans WSLg. Le paquet `keepassxc-full` inclut la CLI et les bibliothèques graphiques, mais n'impose pas d'ouvrir une fenêtre. Les commandes sont décrites dans le [manuel officiel](https://github.com/keepassxreboot/keepassxc/blob/2.7.10/docs/man/keepassxc-cli.1.adoc).

Après activation de `vault` et installation des packages :

```bash
keepassxc-cli --version
# Contrôle d'ouverture : saisir le mot de passe à l'invite, jamais dans la commande.
env -u DISPLAY -u WAYLAND_DISPLAY keepassxc-cli db-info "$HOME/.local/share/keepassxc/vault.kdbx"
# Session interactive facultative ; quitter avec « exit ».
keepassxc-cli open "$HOME/.local/share/keepassxc/vault.kdbx"
```

Pour créer un **nouveau** coffre si tu n'en possèdes pas, choisir un chemin libre :

```bash
install -d -m 700 "$HOME/.local/share/keepassxc"
umask 077
keepassxc-cli db-create --set-password "$HOME/.local/share/keepassxc/vault.kdbx"
```

La saisie demande puis confirme le mot de passe maître. Ce fichier pourra être fourni à `secrets:capture --vault-file`. Si ton coffre existant exige aussi un fichier-clé ou une YubiKey, conserver ce second facteur séparément et utiliser les options KeePassXC correspondantes : le bundle actuel ne le sauvegarde pas. Les fonctions de presse-papiers dépendent de l'intégration graphique ; les commandes d'ouverture et de lecture ci-dessus n'en ont pas besoin. Ne pas envoyer les sorties listant les entrées ou leurs valeurs dans un journal partagé.

### Connexions natives et controle final

Seulement pour les capacités sélectionnées :

```bash
gh auth status --hostname github.com
gcloud auth login
# Pour les applications qui utilisent ADC, si nécessaire :
gcloud auth application-default login
codex login
codex login status
```

Activer ensuite l'intégration de la distro dans Docker Desktop sous Windows via **Settings > Resources > WSL Integration**, puis appliquer le changement. Le diagnostic complet vient en dernier :

```bash
docker info >/dev/null
mise run workstation:doctor
```

Omettre `docker info` si la capacité Docker n'est pas sélectionnée. La récupération de fichiers ne recrée pas les sessions des navigateurs, la MFA ni les autorisations expirées. Le [guide Codex](https://developers.openai.com/codex/auth) décrit son stockage local ; ces caches ne sont pas ajoutés au bundle.

Une WSL créée uniquement pour valider la reprise contient de vraies copies des données restaurées. Après succès, suivre le [nettoyage de la WSL de validation](VALIDATION.md#5-nettoyage-de-la-wsl-de-validation) pour fermer ses sessions, retirer son intégration Docker et la désinscrire explicitement.

## Sauvegarde et rotation

Sauvegarder le bundle après chaque modification et tester sa récupération dans un compte ou une WSL jetable. Le mot de passe GitHub et ses moyens de récupération doivent aussi être accessibles sans ce dépôt privé : sa copie hors ligne évite une dépendance circulaire.

En cas de compromission, révoquer d'abord les accès concernés. Changer la clé age et rechiffrer la version courante ne rend pas indéchiffrables les anciens commits pour quelqu'un qui possède l'ancienne clé. Renouveler aussi les secrets exposés et traiter l'historique privé selon le périmètre de l'incident.

## Maintenance quotidienne

`sysupdate` met Ubuntu à jour. `devupdate` actualise mise, ses outils, les repos shell et Codex si activé. Ces opérations peuvent modifier les lockfiles : examiner et tester les changements avant commit. `devclean` inspecte les installations supprimables et nettoie le cache ; `dockerclean` ne supprime pas les volumes.

Après le premier bootstrap avec `wsl`, enregistrer le travail puis exécuter `wsl --shutdown` dans PowerShell Windows et rouvrir Ubuntu. Cela arrête toutes les distributions WSL. La condition installée empêche `systemd-binfmt` de s'exécuter sous WSL ; son état inactive/skipped est attendu. Vérifier ensuite `systemctl is-system-running` et `mise run workstation:doctor --bootstrap`. L'agent SSH peut avoir perdu ses clés : utiliser `sshunlock` si la capacité GitHub est active.
