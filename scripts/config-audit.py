#!/usr/bin/env python3
"""Summarize native mise state; optionally inventory local configuration files."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_FILES = (
    (".gitconfig", "portable preferences can join the shared Git config"),
    (".config/git/identity.conf", "personal identity; capture covers name/email"),
    (".config/git/allowed_signers", "local signing trust"),
    (".config/git/ignore", "global ignore preferences"),
    (".ssh/config", "SSH rules; not captured by secrets:capture"),
    (".codex/config.toml", "preferences and local project trust"),
    (".codex/AGENTS.md", "global instructions"),
    (".vscode-server/data/Machine/settings.json", "WSL editor preferences"),
    (".config/gh/config.yml", "CLI preferences and aliases"),
    (".config/gcloud/configurations/config_default", "account and project choices"),
    (".docker/config.json", "Desktop integration; may contain credentials"),
    (".config/keepassxc/keepassxc.ini", "preferences separate from the KDBX"),
    (".npmrc", "registry preferences; may contain tokens"),
    (".config/pnpm/rc", "registry preferences; may contain tokens"),
    (".cargo/config.toml", "build preferences"),
    (".aws", "local or Windows account configuration"),
    (".azure", "local or Windows account configuration"),
)
PORTABLE_GIT_GROUPS = {
    "alias",
    "core",
    "delta",
    "diff",
    "fetch",
    "init",
    "interactive",
    "merge",
    "pull",
    "push",
    "rebase",
    "rerere",
}


def label(value, home):
    value = str(value)
    return "~" + value[len(str(home)) :] if value.startswith(str(home) + "/") else value


def issues(data, home):
    """Extract identifiers and status only, never current/desired contents or reasons."""
    rows = []
    for category in ("files", "services", "user_services", "accounts", "firewall", "compose"):
        for item in data.get(category, []):
            action = item.get("action", "unknown")
            if action == "noop":
                continue
            identifier = item.get("id", {})
            rows.append(
                (
                    "UNKNOWN" if action == "unknown" else "DRIFT",
                    label(identifier.get("name", category), home),
                    category,
                )
            )
    for item in data.get("repos", []):
        if item.get("state") != "current":
            rows.append(
                (
                    "DRIFT",
                    label(item.get("path_raw", item.get("path", "repository")), home),
                    "repository",
                )
            )
    for item in data.get("dotfiles", {}).get("files", []):
        if item.get("state") != "applied":
            rows.append(("DRIFT", label(item.get("target", "dotfile"), home), "dotfile"))
    for item in data.get("dotfiles", {}).get("edits", []):
        if item.get("state") != "applied":
            rows.append(("DRIFT", label(item.get("target", "dotfile edit"), home), "dotfile edit"))
    for manager, details in data.get("packages", {}).items():
        if not details.get("available", False):
            rows.append(("UNKNOWN", manager, "package manager"))
        for item in details.get("packages", []):
            present = item.get("desired_state", "present") == "present"
            healthy = item.get("state") == ("installed" if present else "absent")
            if not healthy:
                rows.append(("DRIFT", item.get("package", manager), "package"))
    for item in data.get("tools", []):
        if not item.get("installed", False):
            rows.append(("DRIFT", item.get("tool", "tool"), "tool"))
    shell = data.get("login_shell")
    if shell and shell.get("state") != "set":
        rows.append(("DRIFT", "login shell", "user"))
    return rows


def inventory(root, home):
    rows = [
        ("LOCAL", "~/" + relative, guidance)
        for relative, guidance in LOCAL_FILES
        if (home / relative).exists() or (home / relative).is_symlink()
    ]
    for name in ("miserc.toml", "config.local.toml"):
        if (root / name).exists():
            rows.append(("LOCAL", name, "ignored by Git; not captured"))
    if Path("/etc/wsl.conf").exists():
        rows.append(("LOCAL", "/etc/wsl.conf", "systemd and default user preferences"))
    gitconfig = home / ".gitconfig"
    if gitconfig.is_file():
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}
        result = subprocess.run(
            ["git", "config", "--file", str(gitconfig), "--no-includes", "--name-only", "--list"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if not result.returncode:
            groups = {
                key.split(".", 1)[0] for key in result.stdout.splitlines()
            } & PORTABLE_GIT_GROUPS
            if groups:
                rows.append(
                    (
                        "REVIEW",
                        "~/.gitconfig",
                        "portable groups outside Git tracking: " + ", ".join(sorted(groups)),
                    )
                )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 for native drift or unknown state"
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="also list known local files; this does not detect their changes",
    )
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["mise", "-C", str(ROOT), "bootstrap", "status", "--missing", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise ValueError("Native status failed")
        data = json.loads(result.stdout)
        rows = issues(data, Path.home())
        if result.returncode and not rows:
            rows.append(
                ("DRIFT", "bootstrap", "native mise reports a resource requiring attention")
            )
        for status, name, category in rows:
            print(f"[{status}] {name} ({category})")
        if rows:
            print(
                f"{len(rows)} managed item(s) require attention. Compare before applying bootstrap."
            )
        else:
            print("Managed configuration is in its desired state.")
        if args.inventory:
            print("\nLocal inventory: presence only, not detected changes or backups.")
            for status, name, guidance in inventory(ROOT, Path.home()):
                print(f"[{status}] {name}: {guidance}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print(
            "Cannot inspect native mise state. Run mise bootstrap status --missing locally for details.",
            file=sys.stderr,
        )
        return 2
    return 1 if args.check and (result.returncode or rows) else 0


if __name__ == "__main__":
    sys.exit(main())
