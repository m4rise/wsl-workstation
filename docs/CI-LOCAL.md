# Valider la CI localement

[README](../README.md) · [Validation](VALIDATION.md) · [Maintenance](MAINTENANCE.md) · [Politique WSL](WSL.md)

Ce parcours permet de reproduire les contrôles sans crédit GitHub Actions. Il utilise un conteneur Linux et une nouvelle distribution WSL, avec des données fictives. Les vérifications des actions GitHub elles-mêmes et un nouveau boot de la VM WSL restent propres au runner Windows.

Prérequis : le checkout de ce projet, ses outils de test, Docker Desktop accessible depuis WSL, et Windows avec `wsl --install --name` disponible. Le conteneur et la distro téléchargent des packages et des outils ; prévoir réseau et espace disque. Garder les terminaux ouverts pour conserver les variables du parcours. Exécuter chaque étape dans le terminal indiqué et s'arrêter au premier échec.

## 1. Préparer le commit et l'export dans Ubuntu

Commiter d'abord les modifications à valider selon [Validation](VALIDATION.md#2-validation-distante-du-bon-commit). L'export ci-dessous prend **HEAD**, pas les modifications locales. Vérifier le SHA et l'état du checkout :

```bash
cd "$HOME/.config/mise"
git status --short
git rev-parse HEAD
mise -E secrets install --locked
mise run workstation:check
ci_root=$(mktemp -d /tmp/workstation-ci.XXXXXX)
git rev-parse HEAD >"$ci_root/source-sha.txt"
mise run publication:prepare --ref HEAD --output "$ci_root/public"
mise run publication:check --output "$ci_root/public"
tar -C "$ci_root" -czf "$ci_root/public.tar.gz" public public.manifest.json
```

Le manifeste vérifie contenu, modes exécutables et absence d'historique/remote dans l'export. Cette copie publique ne contient ni sélection locale, ni authentification. Conserver le SHA et les journaux avec les résultats de la PR.

Le job Linux teste aussi la publication d'un commit. Créer pour cela un commit **dans une seconde copie jetable**, distincte de l'export WSL et du dépôt de travail :

```bash
cp -a "$ci_root/public" "$ci_root/candidate"
git -C "$ci_root/candidate" add --all
git -C "$ci_root/candidate" \
  -c user.name='CI Fixture' -c user.email=ci-fixture@example.invalid \
  -c commit.gpgsign=false commit -m 'test: isolated CI snapshot'
```

Ce commit local reprend les mêmes fichiers et modes ; son SHA diffère du commit source. L'export `public` conserve son historique vide pour la vérification WSL.

## 2. Reproduire le job Linux dans Docker

Toujours dans Ubuntu, créer le script de contrôle dans le répertoire temporaire :

```bash
cat >"$ci_root/linux-ci.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 zsh openssh-client
ci_checkout=$(mktemp -d /tmp/ci-checkout.XXXXXX)
cp -a /inputs/candidate/. "$ci_checkout/"
chown -R root:root "$ci_checkout"
cd "$ci_checkout"
export MISE_CONFIG_DIR="$ci_checkout"
export MISE_GLOBAL_CONFIG_ROOT="$ci_checkout"
export MISE_ENV=secrets
export MISE_ENABLE_TOOLS=shellcheck,shfmt,actionlint,gitleaks,lychee,taplo,ruff,age,github:jdx/fnox
export MISE_TASK_RUN_AUTO_INSTALL=false
export PYTHONDONTWRITEBYTECODE=1
python3 scripts/install-mise.py
export PATH="$HOME/.local/bin:$PATH"
mise install --locked
mise run workstation:lint
mise run security:audit
mise -E secrets run workstation:test
ci_export=$(mktemp -d /tmp/ci-export.XXXXXX)
mise run publication:prepare --output "$ci_export/public"
mise run publication:check --output "$ci_export/public"
export MISE_CONFIG_DIR="$ci_export/public"
export MISE_GLOBAL_CONFIG_ROOT="$ci_export/public"
export MISE_STATE_DIR="$ci_export/state"
export MISE_CACHE_DIR="$ci_export/cache"
export MISE_TRUSTED_CONFIG_PATHS="$ci_export/public"
cd "$MISE_CONFIG_DIR"
mise run workstation:lint
mise -E secrets run workstation:test
BASH

(
    set -o pipefail
    docker run --rm \
      --mount "type=bind,src=$ci_root/candidate,dst=/inputs/candidate,readonly" \
      --mount "type=bind,src=$ci_root/linux-ci.sh,dst=/inputs/linux-ci.sh,readonly" \
      ubuntu:26.04 bash /inputs/linux-ci.sh 2>&1 | tee "$ci_root/linux-ci.log"
)
```

Le conteneur utilise la version mise des métadonnées du projet et les outils verrouillés. Les tests doivent réussir sur les sources et leur export. KeePassXC peut être explicitement ignoré sur ce job Linux ; il sera obligatoire dans le profil personnel WSL. `pipefail` conserve un échec du conteneur malgré l'écriture du journal. Le conteneur est supprimé automatiquement à la fin.

## 3. Préparer une WSL jetable depuis PowerShell

Dans Ubuntu, afficher le chemin Windows de l'archive créée à l'étape 1 :

```bash
wslpath -w "$ci_root/public.tar.gz"
```

Dans **PowerShell Windows**, saisir ce chemin à l'invite. Le copier dans le dossier temporaire Windows rend l'archive accessible à la nouvelle distro. Son nom est généré pour éviter de réutiliser une installation existante :

```powershell
$ErrorActionPreference = 'Stop'
$archiveSource = Read-Host 'Chemin Windows affiche par wslpath'
$ciWindows = Join-Path $env:TEMP ('workstation-ci-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $ciWindows | Out-Null
$archiveWindows = Join-Path $ciWindows 'public.tar.gz'
Copy-Item -LiteralPath $archiveSource -Destination $archiveWindows
$distro = 'Workstation-CI-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$distro | Set-Content (Join-Path $ciWindows 'distro.txt')
wsl --list --verbose
wsl --install --distribution Ubuntu-26.04 --name $distro --no-launch --web-download
if ($LASTEXITCODE -ne 0) { throw 'Installation WSL echouee' }
```

## 4. Exécuter le bootstrap et contrôler le nouveau démarrage

Dans la **même fenêtre PowerShell** :

```powershell
$archiveOutput = wsl --distribution $distro --user root --cd / -- wslpath -u $archiveWindows.Replace('\', '/')
if ($LASTEXITCODE -ne 0 -or -not $archiveOutput) { throw 'Archive inaccessible depuis WSL' }
$archiveLinux = ($archiveOutput | Out-String).Trim()
$checkout = '/var/tmp/workstation-export/public'
wsl --distribution $distro --user root --cd / -- mkdir -p /var/tmp/workstation-export
if ($LASTEXITCODE -ne 0) { throw 'Creation du repertoire echouee' }
wsl --distribution $distro --user root --cd / -- tar --no-same-owner -xzf $archiveLinux -C /var/tmp/workstation-export
if ($LASTEXITCODE -ne 0) { throw 'Extraction echouee' }
wsl --distribution $distro --user root --cd / -- bash -c "bash $checkout/.github/scripts/bootstrap-wsl.sh $checkout 2>&1" |
    Tee-Object -FilePath (Join-Path $ciWindows 'wsl-bootstrap.log')
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap CI WSL echoue' }
wsl --terminate $distro
if ($LASTEXITCODE -ne 0) { throw 'Terminaison WSL echouee' }
wsl --distribution $distro --user root --cd / -- bash -c "bash /home/contributor/.config/mise/.github/scripts/check-wsl.sh --after-terminate 2>&1" |
    Tee-Object -FilePath (Join-Path $ciWindows 'wsl-restart.log')
if ($LASTEXITCODE -ne 0) { throw 'Verification apres redemarrage echouee' }
```

La redirection `2>&1` se fait dans Bash pour conserver les messages informatifs de stderr sans les transformer en erreurs PowerShell 5. Le code de sortie WSL reste contrôlé après chaque pipeline.

`/var/tmp` conserve l'export si la distro s'arrête entre deux commandes. `--no-same-owner` donne les fichiers extraits à root pour la vérification Git, comme dans la CI. Le script crée le compte fictif `contributor`, applique les profils générique et personnel, migre un timer legacy inerte et contrôle la convergence. Le second script vérifie un nouveau démarrage de PID 1, systemd `running`, le skip de `systemd-binfmt`, l'interop native, CMD et PowerShell, puis refait l'audit et le doctor sans bootstrap réparateur.

Ce test termine **uniquement la distro jetable**. Les autres distributions maintiennent le kernel partagé en vie : il ne prouve pas un nouveau boot de la VM WSL. Le job Windows `Quality` utilise `wsl --shutdown` et vérifie le changement du `boot_id`. Pour valider un shutdown complet sur le poste, suivre [le parcours WSL](WSL.md#3-verifier-apres-un-shutdown-complet) après avoir enregistré le travail en cours.

## 5. Conserver les preuves et nettoyer

Rapporter le SHA source de l'étape 1, les résultats Linux/WSL, les skips éventuels et la limite du test `--terminate`. Les journaux publics doivent utiliser uniquement les fixtures ; garder les diagnostics du poste personnel séparément.

La commande suivante supprime la distribution créée par ce parcours et toutes ses données. Vérifier son nom puis la désinscrire, dans la même fenêtre PowerShell ; garder les journaux Windows et Linux :

```powershell
$distro
wsl --list --verbose
wsl --unregister $distro
if ($LASTEXITCODE -ne 0) { throw 'Nettoyage WSL echoue' }
$ciWindows
```

Si les crédits Actions manquent, conserver la PR en brouillon et placer `[skip ci]` dans chaque commit poussé pour éviter les événements push/pull_request. [GitHub documente cette option et les checks qui restent en attente](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs). Les validations locales ne constituent pas un succès Actions. Avant fusion, déclencher `Quality` sur le SHA final quand les crédits sont disponibles et vérifier les deux jobs selon [Validation](VALIDATION.md#2-validation-distante-du-bon-commit).
