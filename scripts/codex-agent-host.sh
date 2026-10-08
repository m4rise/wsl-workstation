#!/usr/bin/env bash
# Experimental VS Code Agent Host Codex SDK layout, backed by standalone CLI.
set -euo pipefail
mode="${1:-ensure}"
if (($# > 1)) || [[ "$mode" != ensure && "$mode" != check ]]; then
    echo "Usage: codex-agent-host.sh [ensure|check]" >&2
    exit 2
fi
codex_bin="$HOME/.local/bin/codex"
agent_bin="$HOME/.local/share/vscode-codex-sdk/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
if [[ ! -x "$codex_bin" ]]; then
    echo "ERROR: Codex CLI missing at $codex_bin" >&2
    exit 1
fi
if [[ -L "$agent_bin" ]]; then
    if [[ "$(readlink "$agent_bin")" != "$codex_bin" ]]; then
        echo "ERROR: unexpected Agent Host link target: $agent_bin" >&2
        exit 1
    fi
elif [[ -e "$agent_bin" ]]; then
    echo "ERROR: refusing to replace existing Agent Host file: $agent_bin" >&2
    exit 1
elif [[ "$mode" == ensure ]]; then
    mkdir -p "$(dirname "$agent_bin")"
    ln -s "$codex_bin" "$agent_bin"
else
    echo "ERROR: missing Agent Host link: $agent_bin" >&2
    exit 1
fi
if [[ ! -x "$agent_bin" ]]; then
    echo "ERROR: Agent Host link is not executable" >&2
    exit 1
fi
echo "==> VS Code Codex Agent Host: $("$agent_bin" --version)"
