#!/usr/bin/env python3
"""Workstation release lifecycle; Hermes Runner Linux owns mission execution."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ".workstation-hermes.json"


def metadata():
    value = json.loads((ROOT / "system/hermes/release.json").read_text())
    if value["schema"] != 1 or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
        raise ValueError("Release digest is not finalized; refuse provisioning")
    return value


def path(value):
    return Path(os.path.abspath(Path(value).expanduser()))


def no_links(value):
    if any(part.is_symlink() for part in (value, *value.parents)):
        raise ValueError("Symlink destination refused: " + str(value))


def digest(file):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(file, value):
    no_links(file)
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def tree(directory):
    result = {}
    for file in sorted(directory.rglob("*")):
        if file.is_symlink():
            raise ValueError("Unexpected link in component: " + str(file))
        if file.is_file():
            result[str(file.relative_to(directory))] = digest(file)
    return result


def installed(directory):
    no_links(directory)
    receipt = json.loads((directory / RECEIPT).read_text())
    if receipt["schema"] != 1 or tree(directory / "component") != receipt["component_files"]:
        raise ValueError("Installed component integrity mismatch")
    marker = json.loads((directory / ".hrl-install.json").read_text())
    if marker["component"] != receipt["release"]["version"]:
        raise ValueError("Installed component version mismatch")
    if marker["hermes"]["revision"] != receipt["release"]["hermes_revision"]:
        raise ValueError("Installed Hermes pin mismatch")
    return receipt


def tool(name):
    expected = metadata()
    backend = {"python": "python", "codex": "aqua:openai/codex", "gh": "github:cli/cli"}[name]
    result = subprocess.check_output(
        ["mise", "-E", "hermes-tools", "which", name, "--tool", backend + "@" + expected[name]],
        text=True,
    ).strip()
    binary = path(result)
    if not binary.is_file():
        raise ValueError("mise tool missing: " + name)
    return binary


def tool_environment():
    directories = dict.fromkeys(str(tool(name).parent) for name in ("codex", "gh", "python"))
    return dict(os.environ, PATH=os.pathsep.join([*directories, os.environ["PATH"]]))


def prerequisites():
    for command in ("git", "bwrap", "rg", "make", "docker"):
        if not shutil.which(command):
            raise ValueError("Missing Linux prerequisite: " + command)
    subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
    python, codex, gh = tool("python"), tool("codex"), tool("gh")
    expected = metadata()
    for binary, version in (
        (python, "Python " + expected["python"]),
        (codex, "codex-cli " + expected["codex"]),
    ):
        if subprocess.check_output([str(binary), "--version"], text=True).strip() != version:
            raise ValueError("Unexpected tool version: " + str(binary))
    if (
        not subprocess.check_output([str(gh), "--version"], text=True)
        .splitlines()[0]
        .startswith("gh version " + expected["gh"] + " ")
    ):
        raise ValueError("Unexpected tool version: " + str(gh))
    return python, codex


def extract(archive, destination, prefix=None, safe_links=False):
    """Source archives are regular files; quarantine permits data-filtered internal links."""
    with tarfile.open(archive) as source:
        members = source.getmembers()
        names = set()
        for member in members:
            relative = Path(member.name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not relative.parts
                or not (
                    member.isfile()
                    or member.isdir()
                    or safe_links
                    and (member.issym() or member.islnk())
                )
                or member.name in names
            ):
                raise ValueError("Unsafe archive member: " + member.name)
            if prefix and relative.parts[0] != prefix:
                raise ValueError("Unexpected distribution root")
            names.add(member.name)
        source.extractall(destination, members=members, filter="data")


def install(args):
    expected = metadata()
    archive, destination = path(args.archive), path(args.destination)
    no_links(destination)
    if digest(archive) != expected["sha256"]:
        raise ValueError("Distribution SHA256 mismatch")
    if destination.exists():
        receipt = installed(destination)
        if receipt["release"] != expected:
            raise ValueError("Different release exists; choose a new destination")
        print("Already installed and unchanged:", destination)
        return
    python, _ = prerequisites()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="hermes-source-", dir=destination.parent) as temporary:
        source = Path(temporary)
        name = "hermes-runner-linux-" + expected["version"]
        extract(archive, source, name)
        source /= name
        lock = json.loads((source / "vendor/hermes-lock.json").read_text())
        if (
            lock["revision"] != expected["hermes_revision"]
            or lock["sha256"] != expected["hermes_sha256"]
            or lock["patches"]
        ):
            raise ValueError("Distribution Hermes identity mismatch")
        subprocess.run(
            [str(python), str(source / "tools/install.py"), str(destination)], check=True
        )
    os.chmod(destination, 0o700)
    write_new(
        destination / RECEIPT,
        {"schema": 1, "release": expected, "component_files": tree(destination / "component")},
    )
    installed(destination)
    print("Installed release; configuration and data are separate:", destination)


def fetch(args):
    expected = metadata()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise ValueError("Use an approved OWNER/REPOSITORY for the component release")
    destination = path(args.destination)
    no_links(destination)
    if destination.exists():
        if digest(destination) != expected["sha256"]:
            raise ValueError("Existing archive SHA256 mismatch; no replacement")
        print("Archive already verified:", destination)
        return
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="hermes-fetch-", dir=destination.parent) as temporary:
        subprocess.run(
            [
                str(tool("gh")),
                "release",
                "download",
                "v" + expected["version"],
                "--repo",
                args.repository,
                "--pattern",
                expected["archive"],
                "--dir",
                temporary,
            ],
            check=True,
        )
        archive = Path(temporary) / expected["archive"]
        if digest(archive) != expected["sha256"]:
            raise ValueError("Downloaded distribution SHA256 mismatch")
        with (
            os.fdopen(
                os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as target,
            archive.open("rb") as source,
        ):
            shutil.copyfileobj(source, target)
    print("Downloaded and verified release archive:", destination)


def configure(args):
    release, config, data = path(args.installation), path(args.config), path(args.data)
    installed(release)
    for selected in (config, data):
        no_links(selected)
        if selected.is_relative_to(release):
            raise ValueError("Configuration and data must be outside the installation")
    if config.is_relative_to(data):
        raise ValueError("Configuration must be outside mission data")
    if config.exists() or data.exists():
        raise ValueError("Configuration/data already exist; use init for repeat checks")
    _, codex = prerequisites()
    sdd = path(args.sdd_home)
    expected = metadata()
    value = json.loads((release / "component/examples/sulu.json").read_text())
    value.update(
        data=str(data),
        hermes=str(release / "hermes"),
        python=str(release / "venv/bin/python"),
        repository=str(path(args.repository)),
        github_repository=args.github_repository,
        codex=str(codex),
        codex_auth=str(path(args.codex_auth)),
        model=args.model,
        effort=args.effort,
        sdd_package=str(
            sdd / "plugins/cache/engineering-sdd/engineering-sdd" / expected["sdd_version"]
        ),
        sdd_marketplace=str(sdd / ".tmp/marketplaces/engineering-sdd"),
        sdd_pin=expected["sdd_pin"],
        compose_prefix=args.compose_prefix,
        autonomy=args.autonomy,
        runner=args.runner,
    )
    if args.allow_path:
        value["write_paths"] = args.allow_path
    write_new(config, value)
    print("Configuration created; run hermes:run --config", config, "init, then doctor")


def config_path(args):
    if not args.config:
        raise ValueError("Use --config or WORKSTATION_HERMES_CONFIG")
    return path(args.config)


def configuration_release(config):
    value = json.loads(config.read_text())
    return path(config.parent / os.path.expandvars(os.path.expanduser(value["hermes"]))).parent


def run(args, extra):
    config = config_path(args)
    release = configuration_release(config)
    installed(release)
    return subprocess.call(
        [str(release / "component/bin/hrl"), "--config", str(config), *extra],
        env=tool_environment(),
    )


def restore(args):
    destination = path(args.destination)
    no_links(destination)
    if destination.exists():
        raise ValueError("Restore destination exists")
    archive = path(args.backup)
    with tarfile.open(archive) as source:
        if not {"config.json", "data"}.issubset(source.getnames()):
            raise ValueError("Not a Hermes backup")
        if any(
            Path(member.name).parts[0] not in ("config.json", "data")
            for member in source.getmembers()
        ):
            raise ValueError("Unexpected backup contents")
    destination.mkdir(parents=True, mode=0o700)
    try:
        extract(archive, destination, safe_links=True)
        for file in destination.rglob("*"):
            if not file.is_symlink():
                file.chmod(0o700 if file.is_dir() or file.stat().st_mode & 0o111 else 0o600)
        (destination / "config.json").rename(destination / "source-config.review.json")
        write_new(
            destination / "RESTORE-REVIEW-REQUIRED.json",
            {
                "schema": 1,
                "backup_sha256": digest(archive),
                "activated": False,
                "decision": "Compare current revocations, ledger and skills before restoring state. "
                "Review source paths; no active configuration was created or changed.",
            },
        )
    except BaseException:
        shutil.rmtree(destination)
        raise
    print("Restored in quarantine only; inspect governance before activation:", destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        item = sub.add_parser(name, help="Install a verified release in an explicit new directory")
        item.add_argument("--archive", required=True)
        item.add_argument("--destination", required=True)
    item = sub.add_parser(
        "fetch", help="Fetch the pinned asset from an approved component repository"
    )
    item.add_argument("--repository", required=True)
    item.add_argument("--destination", required=True)
    sub.add_parser("dependencies", help="Install pinned user tools through mise, never apt/sudo")
    item = sub.add_parser("sdd-install")
    item.add_argument("--installation", required=True)
    item.add_argument("--home", required=True)
    item = sub.add_parser("configure")
    for name in (
        "installation",
        "config",
        "data",
        "repository",
        "github-repository",
        "codex-auth",
        "sdd-home",
    ):
        item.add_argument("--" + name, required=True)
    item.add_argument("--runner", choices=("codex-linux",), default="codex-linux")
    item.add_argument("--model", default="gpt-6-astra")
    item.add_argument("--effort", choices=("low", "medium", "high", "xhigh"), default="high")
    item.add_argument(
        "--autonomy",
        choices=("observation-with-validation", "development-isolated"),
        default="observation-with-validation",
    )
    item.add_argument("--allow-path", action="append", default=[])
    item.add_argument("--compose-prefix", default="cms-ci-hrl8")
    item = sub.add_parser("run", help="Pass remaining arguments unchanged to the component")
    item.add_argument("--config", default=os.environ.get("WORKSTATION_HERMES_CONFIG"))
    item.add_argument("arguments", nargs=argparse.REMAINDER)
    item = sub.add_parser("backup")
    item.add_argument("--config", default=os.environ.get("WORKSTATION_HERMES_CONFIG"))
    item.add_argument("--destination", required=True)
    item = sub.add_parser("restore", help="Extract a backup in a new quarantine; never activate")
    item.add_argument("--backup", required=True)
    item.add_argument("--destination", required=True)
    item = sub.add_parser("uninstall")
    item.add_argument("--installation", required=True)
    item.add_argument("--config", required=True)
    args = parser.parse_args()
    if os.environ.get("WORKSTATION_HERMES") != "1":
        parser.error("Select the hermes capability explicitly")
    try:
        if args.command in ("install", "update"):
            install(args)
            if args.command == "update":
                print("No activation. Qualify with fresh data, then use adopt-config explicitly.")
        elif args.command == "fetch":
            fetch(args)
        elif args.command == "dependencies":
            subprocess.run(
                [
                    "mise",
                    "-E",
                    "hermes-tools",
                    "install",
                    "--locked",
                    "python",
                    "aqua:openai/codex",
                    "github:cli/cli",
                ],
                check=True,
            )
            prerequisites()
        elif args.command == "configure":
            configure(args)
        elif args.command == "sdd-install":
            release = path(args.installation)
            installed(release)
            python, _ = prerequisites()
            env = tool_environment()
            subprocess.run(
                [
                    str(python),
                    str(release / "component/tools/install-sdd.py"),
                    str(path(args.home)),
                ],
                env=env,
                check=True,
            )
        elif args.command == "run":
            return run(args, args.arguments)
        elif args.command == "backup":
            return run(args, ["backup", str(path(args.destination))])
        elif args.command == "restore":
            restore(args)
        elif args.command == "uninstall":
            release = path(args.installation)
            installed(release)
            if configuration_release(path(args.config)) != release:
                raise ValueError("Selected configuration does not use this installation")
            subprocess.run(
                [
                    str(release / "venv/bin/python"),
                    str(release / "component/tools/uninstall.py"),
                    str(release),
                    "--config",
                    str(path(args.config)),
                ],
                check=True,
            )
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        print("Hermes lifecycle:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
