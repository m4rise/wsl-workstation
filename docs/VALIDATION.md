# Validation pas a pas

[README](../README.md) · [Operations](OPERATIONS.md) · [Maintenance](MAINTENANCE.md)

Les étapes 1 et 2 concernent toute contribution. Les étapes 3 à 5 sont facultatives : elles valident une **reprise personnelle réelle** depuis un bundle privé. Un test automatisé avec des clés fictives ne démontre pas que tes propres sauvegardes sont récupérables. Exécuter une étape à la fois et arrêter si elle échoue. Ne jamais transmettre de clé privée, jeton, mot de passe ou contenu du coffre.

## 1. Controle sur le poste actuel

Dans ta WSL habituelle :

```bash
cd "$HOME/.config/mise"
mise -E secrets install --locked
mise run workstation:check
mise run workstation:config-audit --check
mise run workstation:doctor
```

Les alias `devlint`, `devaudit` et `devdoctor` sont équivalents. Le résultat attendu est aucun échec ; lire les avertissements. Si KeePassXC n'est pas installé, son test est signalé comme ignoré ici et sera obligatoire dans le job WSL personnel. Cette étape ne restaure aucun secret sur ton compte.

## 2. Validation distante du bon commit

Les modifications locales ne sont pas visibles par GitHub Actions. Sur un dépôt public, travailler dans son fork ; avant publication, utiliser le dépôt privé existant. Ne jamais rendre public son ancien historique. Se placer dans la branche de travail choisie, sans recréer une branche déjà existante :

```bash
git branch --show-current
git diff --check
git status --short
git diff --stat
```

Relire aussi le contenu des nouveaux fichiers, absent de `git diff`. Ajouter uniquement les chemins effectivement revus avec `git add -- CHEMIN1 CHEMIN2`, puis vérifier :

```bash
git diff --cached --check
git diff --cached --stat
git diff --cached
```

Vérifier que `config.local.toml`, `miserc.toml`, l'identité locale, le bundle et ses clés ne figurent pas dans l'index. Ne pas oublier les nouveaux exemples, outils, configurations ou fichiers système voulus. Puis, adapter le message au changement et pousser la branche courante :

```bash
git commit -m "fix: describe the reviewed change"
branch=$(git branch --show-current)
test -n "$branch"
git push -u origin "$branch"
# Créer la PR seulement si elle n'existe pas ; sur un fork, choisir le dépôt cible.
gh pr create --base main --fill
git rev-parse HEAD
gh run list --workflow quality.yml --branch "$branch" --limit 5 \
  --json databaseId,headSha,status,conclusion,url
```

Une PR déclenche la CI ; un push de branche seule peut aussi être testé via l'onglet Actions, workflow `Quality`, bouton **Run workflow**, en sélectionnant cette branche. Sur un fork, activer d'abord ses Actions si GitHub le demande et vérifier dans le dépôt où s'exécute le run.

Choisir le run dont `headSha` correspond au commit affiché, puis saisir son `databaseId` :

```bash
read -r run_id
gh run watch "$run_id" --exit-status
gh run view "$run_id" --json url,headSha,conclusion,jobs
# Seulement en cas d'échec :
gh run view "$run_id" --log-failed
```

Les jobs `checks` et `bootstrap-wsl` doivent réussir. Le second installe les profils générique et personnel, vérifie leur convergence, l'audit et les tests WSL/KeePassXC. Après `wsl --shutdown`, il vérifie systemd `running` et relance le doctor. Le runner reste sur Windows pendant cet arrêt. Ce contrôle ne remplace pas la vérification locale de Docker Desktop et des comptes réels. Fournir le lien et le SHA, ou le journal d'échec : un succès sur un autre SHA ne valide pas les modifications courantes.

Si Actions est indisponible, conserver la PR en brouillon avec des commits `[skip ci]` et rapporter les résultats des contrôles locaux. Exécuter les deux jobs sur le SHA final avant fusion quand Actions redevient disponible.

## 3. Premiere sauvegarde personnelle

Sur le poste actuel, suivre [Première capture](OPERATIONS.md#premiere-capture) :

1. Activer `secrets` et `github` ; ajouter `vault` si tu souhaites utiliser KeePassXC dans Linux. `personal` sélectionne toutes les capacités ; pour préserver une sélection partielle, donner la liste complète souhaitée.
2. Lancer `secrets:init` avec le chemin choisi pour la clé age. Un bundle déjà initialisé ne doit pas être réinitialisé.
3. Faire les deux sauvegardes hors ligne de la clé, dans des emplacements séparés. Vérifier leur déchiffrement sans afficher leur contenu. En l'absence temporaire de support hors ligne, suivre le repli chiffré côté client documenté dans Operations, conserver sa phrase distincte sur papier et planifier une copie physique.
4. Capturer ta véritable clé SSH avec `--ssh-key` si tu veux la reprendre ; choisir son chemin réel, pas automatiquement le nom de l'exemple. Ajouter `--vault-file` seulement si un coffre existe déjà.
5. Exécuter `secrets:check`. Ouvrir le coffre via `keepassxc-cli db-info` s'il est inclus. Fournir seulement le statut de réussite, pas les informations affichées sur le coffre.
6. Scanner puis commiter le bundle, conformément à Operations, et le pousser sur **son dépôt privé dédié**. S'il existe déjà, ne pas relancer `gh repo create`.
7. Conserver une copie hors ligne du bundle et le SHA du commit sauvegardé séparément. En l'absence temporaire de support physique, créer l'archive chiffrée côté client décrite dans Operations et la copier sur les deux stockages indépendants. Vérifier la confidentialité du dépôt avec `gh repo view OWNER/REPO --json isPrivate`.

Faire ensuite `secrets:check` avec chacune des copies de clé age, ou avec une copie temporaire protégée sur le système de fichiers Linux si le support ne gère pas les permissions Unix. Leur déchiffrement effectif valide mieux une sauvegarde qu'une simple présence du fichier.

## 4. Reprise dans une WSL distincte

**Ne pas lancer la restauration sur ton compte actuellement configuré.** Elle refusera les fichiers déjà présents ; ne pas les déplacer uniquement pour contourner ce contrôle. Utiliser une nouvelle distro dédiée au test.

Dans PowerShell, vérifier d'abord qu'aucune distro ne porte déjà le nom `Workstation-Recovery`, puis en créer une :

```powershell
wsl --list --verbose
wsl --install Ubuntu-26.04 --name Workstation-Recovery --no-launch --web-download
wsl --distribution Workstation-Recovery
```

L'option `--name` est documentée par [Ubuntu](https://ubuntu.com/wsl/docs/stable/howto/manage-and-configure/). Si une option n'est pas reconnue, fournir la sortie de `wsl --version` et `wsl --help` pour adapter la procédure ; ne pas désinscrire ta distro actuelle. Créer un utilisateur Linux ordinaire, de préférence avec un autre nom que celui du poste source pour détecter les chemins personnels codés en dur, puis vérifier la cible :

```bash
whoami
cat /etc/os-release | grep -E '^(NAME|VERSION)='
```

Dans cette nouvelle WSL, installer les prérequis. Avant publication, `gh` permet de cloner le dépôt source privé ; l'installateur mise sera lancé après ce clone, depuis les mêmes métadonnées que dans le README :

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3 gh
gh --version
```

S'authentifier nativement, contrôler la session, puis cloner :

```bash
gh auth login --hostname github.com --web --git-protocol https
gh auth status --hostname github.com
read -r source_repo  # OWNER/REPO du bootstrap privé, pas du bundle
gh repo clone "$source_repo" "$HOME/.config/mise"
cd "$HOME/.config/mise"
read -r source_ref  # SHA exact du commit validé en CI
git fetch origin "$source_ref"
git switch --detach FETCH_HEAD
git rev-parse HEAD
python3 scripts/install-mise.py
export PATH="$HOME/.local/bin:$PATH"
mise --version
mise trust
mise bootstrap --update --locked
mise run workstation:doctor --bootstrap
mise run profile:select personal
mise bootstrap --update --locked
exec zsh -l
```

Le SHA doit correspondre à celui validé en CI et être conservé avec le SHA du bundle. La présence préalable de `gh` sert ici à accéder au dépôt encore privé ; le test générique sans outil facultatif préinstallé est effectué en CI. Après publication, le clone HTTPS public du README suffira. Dans le nouveau shell, contrôler aussi le profil personnel sans demander les comptes encore absents :

```bash
cd "$HOME/.config/mise"
mise run workstation:doctor --bootstrap
keepassxc-cli --version
```

Si la clé SSH capturée doit retrouver un chemin différent de `~/.ssh/id_ed25519`, créer avant la restauration la configuration locale ignorée par Git. Pour le chemin `~/.ssh/github` :

```bash
cd "$HOME/.config/mise"
cat >config.local.toml <<'EOF'
[env]
WORKSTATION_SSH_KEY = "{{ env.HOME }}/.ssh/github"
EOF
chmod 600 config.local.toml
```

Déchiffrer ensuite la copie age dans le système de fichiers Linux. Adapter seulement le chemin du fichier `.age` :

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
stat -c '%a %U:%G %n' \
  "$HOME/.config/mise/config.local.toml" \
  "$HOME/.config/fnox" \
  "$restored_age_key"
unset encrypted_age_key restored_age_key
```

Le résultat attendu est `600` pour les deux fichiers, `700` pour le répertoire et aucune erreur de `age-keygen`. Omettre la ligne `config.local.toml` du `stat` si le chemin SSH par défaut est conservé.

Appliquer ensuite [Reprise sur une WSL neuve](OPERATIONS.md#reprise-sur-une-wsl-neuve). Choisir `--ssh` et `--vault` uniquement pour les données capturées. Cette commande peut demander la phrase secrète SSH ; le mot de passe maître du coffre reste saisi dans KeePassXC.

Après restauration :

```bash
exec zsh -l
sshunlock
ssh -T git@github.com
# Si un coffre a été restauré :
env -u DISPLAY -u WAYLAND_DISPLAY keepassxc-cli db-info "$HOME/.local/share/keepassxc/vault.kdbx"
mise bootstrap --locked
mise bootstrap status --missing
```

`exec zsh -l` charge Keychain et peut demander immédiatement la phrase secrète de la clé restaurée ; l'appel suivant à `sshunlock` confirme alors son chargement. À la première connexion SSH, vérifier l'empreinte de clé hôte dans la [documentation GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/testing-your-ssh-connection) avant de l'accepter. L'empreinte ED25519 attendue est `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`.

Le message de réussite de `ssh -T` s'accompagne normalement du code 1. L'ouverture du coffre doit réussir avec ton vrai mot de passe maître ; `doctor` ne l'ouvre pas. `mise bootstrap status --missing` peut afficher la table complète : aucune ligne ne doit avoir l'état `missing`.

Reconnecter ensuite les services sélectionnés avec leurs mécanismes natifs. N'exécuter la connexion ADC que si elle est utilisée sur le poste source :

```bash
gh auth status --hostname github.com
gcloud auth login
# Facultatif : gcloud auth application-default login
codex login
codex login status
```

Dans Docker Desktop sous Windows, ouvrir **Settings > Resources > WSL Integration**, activer `Workstation-Recovery`, puis appliquer le changement. De retour dans la WSL :

```bash
docker info >/dev/null
mise run workstation:doctor
```

La reprise est validée quand les fichiers sont utilisables, le deuxième bootstrap converge et le diagnostic n'a aucun échec ni avertissement inexpliqué. Fournir le résultat de `doctor` après revue, le SHA testé et la confirmation d'ouverture du coffre. La publication reste une étape ultérieure.

## 5. Nettoyage de la WSL de validation

La distro de reprise contient maintenant des copies de la clé SSH, du coffre, de la clé age et des sessions. Après avoir conservé les seuls résultats de validation, fermer les sessions locales avant de détruire la distro :

```bash
gh auth logout --hostname github.com
gcloud auth revoke --all
codex logout
ssh-add -D
exit
```

`gh auth logout` supprime la configuration locale, mais [ne révoque pas les jetons GitHub CLI côté serveur](https://cli.github.com/manual/gh_auth_logout). Révoquer toute l'application GitHub CLI déconnecterait aussi les autres postes ; la suppression de cette distro élimine ici sa copie locale. `gcloud auth revoke --all` révoque côté serveur les identifiants utilisateur présents dans cette distro, conformément à la [référence Google Cloud](https://cloud.google.com/sdk/gcloud/reference/auth/revoke).

Dans Docker Desktop, désactiver ensuite `Workstation-Recovery` sous **Settings > Resources > WSL Integration** et appliquer le changement. Enfin, dans PowerShell, relire le nom avant la commande destructive :

```powershell
wsl --list --verbose
wsl --terminate Workstation-Recovery
wsl --unregister Workstation-Recovery
wsl --list --verbose
```

`wsl --unregister` supprime irréversiblement tout le système de fichiers de cette distro. Ne l'exécuter qu'après validation du nom et après avoir vérifié qu'aucune donnée unique n'y reste. La distro habituelle `Ubuntu-26.04` ne doit jamais être désinscrite pendant ce test.
