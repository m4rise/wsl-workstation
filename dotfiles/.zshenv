# Keep PATH entries unique while preserving priority.
typeset -U path PATH

# Rust / Cargo — optional.
[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
