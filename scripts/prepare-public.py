#!/usr/bin/env python3
"""Export a reviewed Git reference without its history or local configuration."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {".github", "docs", "dotfiles", "scripts", "system", "tasks", "tests", "examples"}
FILES = {
    ".gitattributes",
    ".gitignore",
    ".editorconfig",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "config.toml",
    "mise.lock",
    "ruff.toml",
    "renovate.json",
}
PRIVATE_NAMES = {
    ".env",
    "fnox.toml",
    "miserc.toml",
    "age.txt",
    "identity.conf",
    "allowed_signers",
    "auth.json",
    "hosts.yml",
    "credentials",
}
PLACEHOLDER_USERS = {"contributor", "username", "user"}


class ExportError(Exception):
    pass


def unsafe_path(file):
    return any(part.is_symlink() for part in (file, *file.parents))


def permitted(name):
    relative = Path(name)
    allowed = (
        relative.parts[0] in DIRECTORIES
        or name in FILES
        or (
            len(relative.parts) == 1
            and (
                name.startswith("config.")
                and name.endswith(".toml")
                or name.startswith("mise.")
                and name.endswith(".lock")
            )
        )
    )
    return allowed and not (
        relative.name in PRIVATE_NAMES
        or relative.name.startswith(".env.")
        or ".local." in name
        or name.endswith((".kdbx", ".pem", ".key"))
    )


def git(*arguments):
    return subprocess.check_output(["git", "-C", str(ROOT), *arguments], stderr=subprocess.PIPE)


def entries(reference, working_tree=False):
    commit = (
        git("rev-parse", "--verify", "--end-of-options", reference + "^{commit}").decode().strip()
    )
    if working_tree:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
        for name in sorted(set(names.decode().split("\0")) - {""}):
            source = ROOT / name
            if source.is_symlink() or unsafe_path(source):
                raise ExportError("Symlink source refused")
            if not source.exists():
                continue
            mode = "100755" if source.stat().st_mode & 0o111 else "100644"
            yield commit, name, mode, source.read_bytes()
    else:
        for entry in git("ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
            if not entry:
                continue
            metadata, filename = entry.split(b"\t", 1)
            mode, kind, object_id = metadata.decode().split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ExportError("Only regular versioned files can be exported")
            yield commit, filename.decode(), mode, git("cat-file", "blob", object_id)


def personal_content(content, markers):
    text = content.decode(errors="replace")
    if any(marker and marker in text for marker in markers):
        return True
    # Generic CI/example accounts are intentional. This supplements Gitleaks;
    # names, email addresses and every possible personal value still need review.
    users = re.findall(r"(?<![A-Za-z0-9_./-])(?:/home/|/mnt/[a-z]/Users/)([A-Za-z0-9_.-]+)", text)
    return any(user not in PLACEHOLDER_USERS for user in users)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new directory outside this checkout")
    parser.add_argument(
        "--ref", default="HEAD", help="reviewed Git commit, tag or branch (default: HEAD)"
    )
    parser.add_argument(
        "--working-tree",
        action="store_true",
        help="explicit preview including uncommitted and new non-ignored files",
    )
    parser.add_argument(
        "--markers-file", help="private file outside this checkout, one personal marker per line"
    )
    args = parser.parse_args()
    output = Path(args.output).expanduser().absolute()
    manifest = output.with_name(output.name + ".manifest.json")
    if (
        output.exists()
        or manifest.exists()
        or unsafe_path(output)
        or unsafe_path(manifest)
        or ROOT == output
        or ROOT in output.resolve().parents
    ):
        parser.error("Use a new destination outside this checkout")
    try:
        markers = [str(Path.home()), str(ROOT)]
        if args.markers_file:
            source = Path(args.markers_file).expanduser().absolute()
            if unsafe_path(source) or source == ROOT or ROOT in source.resolve().parents:
                raise ExportError("Personal markers must be stored outside this checkout")
            markers.extend(line.strip() for line in source.read_text().splitlines() if line.strip())
        selected = []
        for commit, name, mode, content in entries(args.ref, args.working_tree):
            if not permitted(name):
                raise ExportError(
                    "Unexpected or private file in export; review the source reference"
                )
            if personal_content(content, markers):
                raise ExportError(
                    f"Personal marker or home path detected in {name}; inspect privately"
                )
            selected.append((name, mode, content))
        if not selected:
            raise ExportError("Source reference contains no exportable files")
    except (OSError, ValueError, subprocess.CalledProcessError, ExportError) as error:
        parser.error(
            str(error)
            if isinstance(error, ExportError)
            else "Cannot read source reference or marker file"
        )
    output.mkdir(mode=0o700, parents=True)
    try:
        records = []
        for name, mode, content in selected:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o755 if mode == "100755" else 0o644)
            records.append(
                {"path": name, "mode": mode, "sha256": hashlib.sha256(content).hexdigest()}
            )
        subprocess.run(["gitleaks", "dir", "--redact", str(output)], check=True)
        subprocess.run(
            ["git", "init", "--initial-branch=main", str(output)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with manifest.open("x") as stream:
            json.dump(
                {
                    "format": 1,
                    "source_commit": commit,
                    "working_tree": args.working_tree,
                    "files": records,
                },
                stream,
                indent=2,
            )
            stream.write("\n")
        manifest.chmod(0o600)
    except (OSError, subprocess.CalledProcessError):
        print(
            "Export failed validation. Do not publish it; inspect the local output. Nothing was published.",
            file=sys.stderr,
        )
        return 1
    print(f"Prepared {len(selected)} files; no commits and no remote. Manifest: {manifest}")
    if args.working_tree:
        print("Working-tree preview: commit and validate the final reference before publication.")
    print(
        "Verify the manifest and review every file. Gitleaks and personal markers are not exhaustive."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
