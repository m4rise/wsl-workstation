#!/usr/bin/env python3
"""Verify an export against its adjacent manifest before committing or publishing."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def verify(output, manifest):
    data = json.loads(manifest.read_text())
    if data["format"] != 1 or not data["files"]:
        raise ValueError("Invalid manifest")
    expected = set()
    for entry in data["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] == ".git":
            raise ValueError("Invalid manifest path")
        if entry["path"] in expected:
            raise ValueError("Duplicate manifest path")
        expected.add(entry["path"])
        target = output / relative
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("Symlink export refused")
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Export file differs from manifest")
        executable = bool(target.stat().st_mode & 0o111)
        if executable != (entry["mode"] == "100755"):
            raise ValueError("Export executable mode differs from manifest")
    actual = {
        p.relative_to(output).as_posix()
        for p in output.rglob("*")
        if (p.is_file() or p.is_symlink()) and p.relative_to(output).parts[0] != ".git"
    }
    if expected != actual:
        raise ValueError("Export file inventory differs from manifest")
    remote = subprocess.check_output(["git", "-C", str(output), "remote"], stderr=subprocess.PIPE)
    commits = subprocess.check_output(
        ["git", "-C", str(output), "rev-list", "--all", "--count"], stderr=subprocess.PIPE
    )
    if remote.strip() or commits.strip() != b"0":
        raise ValueError("Expected an export with no remote and no commits")
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).expanduser().absolute()
    try:
        count = verify(output, output.with_name(output.name + ".manifest.json"))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print(
            "Export verification failed; check files, manifest, modes and Git state before publication.",
            file=sys.stderr,
        )
        return 1
    print(f"Verified {count} export files; no remote and no commits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
