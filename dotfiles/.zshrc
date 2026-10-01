# ==============================================================================
# Early mise and SSH initialization
# ==============================================================================

# Activate mise first so selected capabilities and their tools are available to
# every conditional initialization that follows.
[[ -f "$HOME/.zprofile" ]] && source "$HOME/.zprofile"
eval "$("$HOME/.local/bin/mise" activate zsh)"

# Keychain can request the SSH passphrase, so it must run before the
# Powerlevel10k instant prompt block.
if [[ "${WORKSTATION_GITHUB:-0}" == 1 ]] && command -v keychain >/dev/null 2>&1 &&
    [[ -f "${WORKSTATION_SSH_KEY:-$HOME/.ssh/id_ed25519}" ]]; then
    eval "$(keychain add --eval "${WORKSTATION_SSH_KEY:-$HOME/.ssh/id_ed25519}")"
fi

# ==============================================================================
# Powerlevel10k instant prompt
# ==============================================================================

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
    source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


# ==============================================================================
# Environment / PATH
# ==============================================================================

# Load user-defined PATH settings (e.g. ~/bin, ~/.local/bin) from .zprofile.
# This also makes them available in interactive non-login shells.
if [[ -f "$HOME/.zprofile" ]]; then
    source "$HOME/.zprofile"
fi

# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:$PATH


# ==============================================================================
# Oh My Zsh
# ==============================================================================

# Updates are orchestrated explicitly by mise.
zstyle ':omz:update' mode disabled

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="powerlevel10k/powerlevel10k"

# Set list of themes to pick from when loading at random.
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/.
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior.
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1
# (see #5765).
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status checks for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications.
# See `man strftime` for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder


# ==============================================================================
# Oh My Zsh plugins
# ==============================================================================

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/.
# Custom plugins may be added to $ZSH_CUSTOM/plugins/.
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(
    fzf
    fzf-tab
    git
    zsh-autosuggestions
    zsh-syntax-highlighting
)

[[ "${WORKSTATION_GITHUB:-0}" == 1 ]] && plugins+=(gh)
[[ "${WORKSTATION_CLOUD:-0}" == 1 ]] && plugins+=(gcloud)

source "$ZSH/oh-my-zsh.sh"


# ==============================================================================
# Shell integrations
# ==============================================================================

# zoxide — smart directory navigation.
# Loaded after Oh My Zsh so Zsh completion (compinit) is already initialized.
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init zsh)"
fi

# ==============================================================================
# GPG
# ==============================================================================

# Set GPG_TTY when a real terminal is available.
# This is useful for gpg/git signing in WSL2 and VS Code terminals.
if gpg_tty="$(tty 2>/dev/null)"; then
    export GPG_TTY="$gpg_tty"
fi
unset gpg_tty


# ==============================================================================
# User configuration
# ==============================================================================

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment.
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions.
# if [[ -n $SSH_CONNECTION ]]; then
#     export EDITOR='vim'
# else
#     export EDITOR='mvim'
# fi

# Compilation flags.
# export ARCHFLAGS="-arch x86_64"


# ==============================================================================
# User functions
# ==============================================================================

sshunlock() {
    local key="${WORKSTATION_SSH_KEY:-$HOME/.ssh/id_ed25519}"

    if [[ "${WORKSTATION_GITHUB:-0}" != 1 ]] || ! command -v keychain >/dev/null 2>&1; then
        print -u2 "Enable the github capability to use sshunlock."
        return 1
    fi

    if [[ ! -f "$key" ]]; then
        print -u2 "SSH key not found: $key"
        return 1
    fi

    eval "$(keychain add --eval --immediate "$key")"
}


# ==============================================================================
# Aliases
# ==============================================================================

# Set personal aliases, overriding those provided by Oh My Zsh libs,
# plugins, and themes. Aliases can be placed here, though Oh My Zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases:
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

# bat as enhanced cat, while preserving access to the original cat.
alias cat='bat'
alias rcat='/usr/bin/cat'

# Use bat for man pages.
export MANPAGER="sh -c 'col -bx | bat -l man -p'"
export MANROFFOPT="-c"

# Enhanced directory listings.
alias ll='eza -lah --group-directories-first --git'
alias tree='eza --tree --group-directories-first'

# Custom user aliases
alias cddev='cd "$HOME/dev"'
alias cdmise='cd $HOME/.config/mise'

# ==============================================================================
# Workstation maintenance
# ==============================================================================

alias sysupdate='mise run system:update'
alias devupdate='mise run dev:update && exec zsh -l'
alias devclean='mise run dev:clean'
[[ "${WORKSTATION_DOCKER:-0}" == 1 ]] && alias dockerclean='mise run docker:clean'
alias updateall='mise run update && exec zsh -l'

alias devdoctor='mise run workstation:doctor'
alias devconfig='mise run workstation:config-audit'
alias devcheck='mise run workstation:check'
alias devlint='mise run workstation:lint'
alias devaudit='mise run security:audit'
alias devversions='mise run workstation:versions'
alias devprofile='mise run profile:select'
alias devrestore='mise run secrets:restore'
if [[ "${WORKSTATION_SECRETS:-0}" == 1 && "${WORKSTATION_VAULT:-0}" == 1 ]]; then
    alias devvaultupdate='mise run secrets:vault-update'
fi


# ==============================================================================
# Powerlevel10k configuration
# ==============================================================================

# Powerlevel10k itself is already loaded by Oh My Zsh through:
# ZSH_THEME="powerlevel10k/powerlevel10k"
#
# Do not source powerlevel10k.zsh-theme a second time here.

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ -f "$HOME/.p10k.zsh" ]] && source "$HOME/.p10k.zsh"
