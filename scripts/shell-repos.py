#!/usr/bin/env python3
"""Refresh a reviewed shell snapshot or resume updates after a pinned installation."""

import argparse
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(path, *args):
    return (
        subprocess.check_output(["git", "-C", str(path), *args], stderr=subprocess.PIPE)
        .decode()
        .strip()
    )


def repositories(root=ROOT, home=None):
    home = home or Path.home()
    data = tomllib.loads((root / "config.reproducible.toml").read_text())["bootstrap"]["repos"]
    for name, entry in data.items():
        if (
            not name.startswith("~/")
            or ".." in Path(name).parts
            or not re.fullmatch(r"[0-9a-f]{40}", entry["ref"])
        ):
            raise ValueError("Invalid shell snapshot")
        yield name, home / name[2:], entry


def prepare_update(root=ROOT, home=None):
    for name, path, entry in repositories(root, home):
        if not path.is_dir():
            continue
        try:
            try:
                git(path, "symbolic-ref", "-q", "HEAD")
                continue  # Existing branches retain their ordinary update behavior.
            except subprocess.CalledProcessError:
                pass
            if (
                git(path, "status", "--porcelain")
                or git(path, "rev-parse", "HEAD") != entry["ref"]
                or git(path, "remote", "get-url", "origin") != entry["url"]
            ):
                print(f"Skipped detached or modified repository: {name}")
                continue
            remote_branch = git(path, "symbolic-ref", "refs/remotes/origin/HEAD")
            prefix = "refs/remotes/origin/"
            if not remote_branch.startswith(prefix):
                raise ValueError("Unexpected default branch")
            branch = remote_branch[len(prefix) :]
            git(path, "merge-base", "--is-ancestor", entry["ref"], remote_branch)
            try:
                local_head = git(path, "rev-parse", "--verify", "refs/heads/" + branch)
            except subprocess.CalledProcessError:
                git(path, "switch", "-c", branch, "--track", "origin/" + branch)
            else:
                if local_head not in {entry["ref"], git(path, "rev-parse", remote_branch)}:
                    raise ValueError("Local branch differs from snapshot")
                git(path, "switch", branch)
            print(f"Resumed upstream branch for {name}")
        except (OSError, ValueError, subprocess.CalledProcessError):
            print(f"Could not resume {name}; inspect it locally before updating.")


def freeze(root=ROOT, home=None):
    lines = [
        "# Optional, temporary snapshot: mise -E reproducible bootstrap --update --locked",
        "# Default profiles and updateall continue to follow upstream branches.",
        "[bootstrap.repos]",
    ]
    for name, path, entry in repositories(root, home):
        if (
            git(path, "status", "--porcelain")
            or git(path, "remote", "get-url", "origin") != entry["url"]
        ):
            raise ValueError("Shell repositories must be clean and match their declared origins")
        ref = git(path, "rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            raise ValueError("Invalid repository commit")
        lines.append(f'{json.dumps(name)} = {{ url = {json.dumps(entry["url"])}, ref = "{ref}" }}')
    with tempfile.NamedTemporaryFile(
        mode="w", dir=root, prefix=".shell-snapshot-", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write("\n".join(lines) + "\n")
    try:
        temporary.chmod(0o644)
        os.replace(temporary, root / "config.reproducible.toml")
    finally:
        temporary.unlink(missing_ok=True)
    print("Updated config.reproducible.toml. Review the diff and validate a fresh installation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-update", "freeze"))
    args = parser.parse_args()
    try:
        (freeze if args.command == "freeze" else prepare_update)()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        parser.error("Cannot read or refresh the shell snapshot; inspect the local repositories")


if __name__ == "__main__":
    main()
