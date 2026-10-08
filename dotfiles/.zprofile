[[ -d "$HOME/bin" ]] && path=("$HOME/bin" $path)
[[ -d "$HOME/.local/bin" ]] && path=("$HOME/.local/bin" $path)

# Experimental VS Code Codex Agent Host SDK override, provisioned by mise.
agent_sdk_root="$HOME/.local/share/vscode-codex-sdk"
agent_sdk_bin="$agent_sdk_root/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
if [[ -L "$agent_sdk_bin" && -x "$agent_sdk_bin" ]]; then
    export VSCODE_AGENT_HOST_CODEX_SDK_ROOT="$agent_sdk_root"
fi
unset agent_sdk_root agent_sdk_bin
