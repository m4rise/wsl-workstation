#!/usr/bin/env bash
# Bootstrap a disposable Ubuntu 26.04 WSL distro on a GitHub-hosted Windows runner.

set -euo pipefail

checkout=${1:?expected path to the checked-out repository}
# shellcheck source=/dev/null
source /etc/os-release

if [[ "$ID" != ubuntu || "$VERSION_ID" != 26.04 ]]; then
    echo "Expected Ubuntu 26.04, found $PRETTY_NAME" >&2
    exit 1
fi

if ! grep -qi microsoft /proc/version; then
    echo "Expected a WSL kernel." >&2
    exit 1
fi

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl git sudo python3

python3 "$checkout/scripts/verify-public.py" --output "$checkout"

# Deliberately use a different account name to catch personal paths.
useradd --create-home --shell /bin/bash --user-group contributor
printf 'contributor ALL=(ALL) NOPASSWD:ALL\n' >/etc/sudoers.d/99-contributor-ci
chmod 0440 /etc/sudoers.d/99-contributor-ci
visudo -cf /etc/sudoers.d/99-contributor-ci

install -d -o contributor -g contributor /home/contributor/.config
cp -a "$checkout" /home/contributor/.config/mise
chown -R contributor:contributor /home/contributor/.config/mise

# Use the same verified installer and metadata as the public installation guide.
runuser -l contributor -c 'cd ~/.config/mise && python3 scripts/install-mise.py'

# The disposable account has no password; apply its login shell with sudo.
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise -E reproducible bootstrap --update --locked --yes --skip user'
runuser -l contributor -c 'sudo MISE_CONFIG_DIR=/home/contributor/.config/mise MISE_GLOBAL_CONFIG_ROOT=/home/contributor /home/contributor/.local/bin/mise bootstrap user apply --yes'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise -E reproducible bootstrap status --missing'
runuser -l contributor -c 'cd ~/.config/mise && python3 scripts/shell-repos.py prepare-update'
# Expansion must happen in the contributor's shell.
# shellcheck disable=SC2016
runuser -l contributor -c 'test -n "$(git -C ~/.oh-my-zsh branch --show-current)"'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap --locked --yes'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap status --missing'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run workstation:doctor --bootstrap'
runuser -l contributor -c 'cd ~/.config/mise && zsh -i tests/check-shell.zsh generic'

# Generic bootstrap must not provision optional accounts, services or tools.
test ! -e /etc/apt/sources.list.d/google-cloud-sdk.list
test ! -e /etc/systemd/system/systemd-binfmt.service.d/override.conf
test ! -e /home/contributor/.local/bin/codex
test ! -e /home/contributor/.config/git/identity.conf
runuser -l contributor -c '! ~/.local/bin/mise which gh'

# Exercise the complete personal capability set with the same fresh user,
# including the WSL policy, but without personal authentication.
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run profile:select personal'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap --update --locked --yes'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap --locked --yes'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap status --missing'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run workstation:config-audit --check'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run workstation:doctor --bootstrap'
runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise -E secrets run workstation:test'
runuser -l contributor -c 'cd ~/.config/mise && zsh -i tests/check-shell.zsh personal'
# Expansion belongs to the contributor's shell, not the root shell.
# shellcheck disable=SC2016
runuser -l contributor -c '"$HOME/.local/bin/mise" exec -- keepassxc-cli --version'

test -L /home/contributor/.zshrc
