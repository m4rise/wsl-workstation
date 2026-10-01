#!/usr/bin/env bash
# Sourced by file tasks; mise supplies these flags from config.<capability>.toml.
workstation_require() {
    local flag="WORKSTATION_${1^^}"
    if [[ "${!flag:-0}" != 1 ]]; then
        printf 'Enable %s with: mise run profile:select <capabilities including %s>\n' "$1" "$1" >&2
        return 1
    fi
}
