#!/usr/bin/env python3
"""Persist mise environments without putting personal selection in Git."""

import argparse
import json
import os
from pathlib import Path

CAPABILITIES = ("github", "cloud", "codex", "docker", "wsl", "secrets", "vault")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capabilities", nargs="+", help="generic, personal, or names: " + ", ".join(CAPABILITIES)
    )
    args = parser.parse_args()
    selected = args.capabilities
    if selected == ["generic"]:
        selected = []
    elif selected == ["personal"]:
        selected = list(CAPABILITIES)
    elif any(name not in CAPABILITIES for name in selected):
        parser.error("Use generic/personal alone or a list of supported capabilities")
    selected = list(dict.fromkeys(selected))
    root = Path(os.environ.get("MISE_CONFIG_DIR", Path.home() / ".config/mise"))
    target = root / "miserc.toml"
    # Own only the env assignment; never discard unrelated early mise settings.
    lines = target.read_text().splitlines(keepends=True) if target.exists() else []
    if target.is_symlink():
        parser.error("Refusing a symlink selector")
    import tomllib

    existing = tomllib.loads("".join(lines))
    if "env" in existing:
        # Only our single-line format can be edited without damaging TOML.
        matches = [i for i, line in enumerate(lines) if line.startswith("env = ")]
        if len(matches) != 1 or not lines[matches[0]].strip().endswith("]"):
            parser.error("Existing env selection needs manual editing in miserc.toml")
        lines[matches[0]] = "env = " + json.dumps(selected) + "\n"
    else:
        lines.insert(0, "env = " + json.dumps(selected) + "\n")
    temporary = target.with_name("miserc.toml.tmp")
    with temporary.open("x") as stream:
        stream.write("".join(lines))
    temporary.replace(target)
    print("Selected: " + (", ".join(selected) or "generic"))
    print("Apply with: mise bootstrap --update --locked")
    print(
        "Open a fresh shell afterwards. Selection does not uninstall packages or remove services."
    )


if __name__ == "__main__":
    main()
