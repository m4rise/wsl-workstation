#!/usr/bin/env python3
"""Explicit, file-based recovery. Never load a bundle into the interactive shell."""

import argparse
import base64
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"IDENTITY", "SSH_PRIVATE_KEY", "SSH_PUBLIC_KEY"}
KDBX = bytes.fromhex("03d9a29a67fb4bb5")


class RecoveryError(Exception):
    pass


def run(command, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        # Provider output can contain values. Only the tool name is safe to report.
        raise RecoveryError(
            f"{Path(command[0]).name} failed; check access, input and key without sharing secret output"
        )
    return result.stdout


def path(value):
    result = Path(os.path.abspath(Path(value).expanduser()))
    for part in (result, *result.parents):
        if part.is_symlink():
            raise RecoveryError("Refusing a symlink in a recovery path")
    return result


def outside_public(value):
    result = path(value)
    if result == ROOT or ROOT in result.parents:
        raise RecoveryError("Recovery material must be outside the public repository")
    return result


def secure_dir(directory):
    path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.stat().st_uid != os.getuid():
        raise RecoveryError("Recovery directory must belong to the current user")
    directory.chmod(0o700)


def private_file(filename):
    path(filename)
    if not filename.is_file():
        raise RecoveryError("Required private file is absent")
    info = filename.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) not in (0o400, 0o600):
        raise RecoveryError("Private file must belong to you and have mode 0600 (or 0400)")


def write_new(filename, content):
    path(filename)
    # O_EXCL prevents both replacement and following a last-minute symlink.
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # An incomplete private file must not survive a write/flush failure.
        filename.unlink()
        raise


def load_bundle(bundle):
    if not bundle.is_dir():
        raise RecoveryError("Bundle absent; supply --bundle or fetch it with --repo")
    marker = path(bundle / "bundle.json")
    if json.loads(marker.read_text()) != {"version": 1}:
        raise RecoveryError("Unsupported bundle format")
    config = path(bundle / "fnox.toml")
    return config, validate_config(config.read_bytes())


def validate_config(content):
    data = tomllib.loads(content.decode())
    # Reject executable providers, imports, global overrides and plaintext defaults.
    if set(data) != {"default_provider", "env", "providers", "secrets"}:
        raise RecoveryError("Unexpected fnox configuration; only the recovery schema is accepted")
    if data["default_provider"] != "age" or data["env"] is not False:
        raise RecoveryError("Bundle must use age and env = false")
    if set(data["providers"]) != {"age"}:
        raise RecoveryError("Only the dedicated age provider is accepted")
    provider = data["providers"]["age"]
    if set(provider) != {"type", "recipients"} or provider["type"] != "age":
        raise RecoveryError("Unexpected age provider settings")
    recipients = provider["recipients"]
    if (
        not isinstance(recipients, list)
        or not recipients
        or any(
            not isinstance(item, str) or not re.fullmatch(r"age1[a-z0-9]+", item)
            for item in recipients
        )
    ):
        raise RecoveryError("Expected dedicated age public recipients")
    if not isinstance(data["secrets"], dict) or set(data["secrets"]) - NAMES:
        raise RecoveryError("Unexpected recovery secret name")
    for secret in data["secrets"].values():
        if (
            not isinstance(secret, dict)
            or set(secret) != {"provider", "value"}
            or secret["provider"] != "age"
        ):
            raise RecoveryError("Plaintext defaults and custom secret behavior are forbidden")
        ciphertext = base64.b64decode(secret["value"], validate=True)
        if not ciphertext.startswith(b"age-encryption.org/v1\n"):
            raise RecoveryError("Expected age ciphertext")
    return data


def fnox(config, key, *arguments):
    # Explicit --config still reads the global fnox config unless isolated.
    with tempfile.TemporaryDirectory(prefix="workstation-fnox-") as scratch:
        # Execute the exact bytes we validated, never a second read of the bundle.
        content = config.read_bytes()
        data = validate_config(content)
        require_recipient(data, key)
        snapshot = Path(scratch) / "fnox.toml"
        write_new(snapshot, content)
        env = {k: v for k, v in os.environ.items() if not k.startswith("FNOX_") and k != "RUST_LOG"}
        env.update(FNOX_CONFIG_DIR=scratch, FNOX_AGE_KEY_FILE=str(key), FNOX_PROMPT_AUTH="false")
        result = run(
            ["fnox", "--config", str(snapshot), "--no-daemon", "--non-interactive", *arguments],
            env=env,
        )
        if arguments[0] == "set":
            updated = snapshot.read_bytes()
            validate_config(updated)
            config.write_bytes(updated)
        return result


def require_recipient(data, key):
    private_file(key)
    recipient = run(["age-keygen", "-y", str(key)]).decode().strip()
    if data["providers"]["age"]["recipients"] != [recipient]:
        raise RecoveryError(
            "Bundle recipient must match the dedicated age identity; refusing additional recipients"
        )
    return recipient


def put(config, key, name, content):
    with tempfile.TemporaryDirectory(prefix="workstation-input-") as scratch:
        source = Path(scratch) / "input"
        write_new(source, content)
        fnox(
            config,
            key,
            "set",
            name,
            "--provider",
            "age",
            "--base64-encode",
            "--from-file",
            str(source),
        )


def get(config, key, name):
    # fnox get appends a terminal newline, including with --base64-decode.
    # Decode here to preserve the exact bytes captured with --from-file.
    encoded = fnox(config, key, "get", name, "--if-missing", "error")
    return base64.b64decode(encoded.strip(), validate=True)


def identity_data(value):
    data = json.loads(value)
    if set(data) != {"name", "email"} or any(
        not isinstance(v, str) or not v or any(c in v for c in "\r\n\x00") for v in data.values()
    ):
        raise RecoveryError("Invalid identity data")
    if not re.fullmatch(r"[A-Za-z0-9._+%\-]+@[A-Za-z0-9.\-]+", data["email"]):
        raise RecoveryError(
            "Use a simple email address without whitespace or SSH principal wildcards"
        )
    return data


def vault_bytes(filename):
    content = path(filename).read_bytes()
    if len(content) < 12 or content[:8] != KDBX:
        raise RecoveryError("Expected an encrypted KeePass KDBX database")
    return content


def public_key(filename):
    # OpenSSH prompts on the terminal for a protected key. No passphrase arguments.
    content = run(["ssh-keygen", "-y", "-f", str(filename)])
    return b" ".join(content.split()[:2]) + b"\n"


def git_identity():
    # Read the effective user-level configuration outside every repository.
    # `git config --global` can omit XDG config when ~/.gitconfig exists, while
    # running in this checkout could let repository-local values take priority.
    with tempfile.TemporaryDirectory(prefix="workstation-git-config-") as scratch:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT"}
            and not key.startswith("GIT_CONFIG_KEY_")
            and not key.startswith("GIT_CONFIG_VALUE_")
        }
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        try:
            name = (
                run(["git", "-C", scratch, "config", "--includes", "--get", "user.name"], env=env)
                .decode()
                .strip()
            )
            email = (
                run(["git", "-C", scratch, "config", "--includes", "--get", "user.email"], env=env)
                .decode()
                .strip()
            )
        except RecoveryError:
            raise RecoveryError(
                "Git user.name or user.email is missing from the effective user configuration"
            ) from None
    return identity_data(json.dumps({"name": name, "email": email}))


def initialize(args, bundle, key):
    if bundle.exists() and any(bundle.iterdir()):
        raise RecoveryError("Initialization requires an empty bundle directory")
    if key == bundle or bundle in key.parents:
        raise RecoveryError("The age identity must be stored separately from the bundle")
    secure_dir(key.parent)
    if not key.exists():
        run(["age-keygen", "-o", str(key)])
    private_file(key)
    recipient = run(["age-keygen", "-y", str(key)]).decode().strip()
    if not re.fullmatch(r"age1[a-z0-9]+", recipient):
        raise RecoveryError("Use a dedicated age identity")
    secure_dir(bundle)
    write_new(bundle / "bundle.json", b'{"version": 1}\n')
    text = f'default_provider = "age"\nenv = false\n\n[providers.age]\ntype = "age"\nrecipients = ["{recipient}"]\n\n[secrets]\n'
    write_new(bundle / "fnox.toml", text.encode())
    write_new(bundle / ".gitignore", b"age.txt\n*.key\n*.pem\n.env\n*.local.toml\n*.tmp\n")
    write_new(
        bundle / "README.md",
        b"# Private recovery bundle\n\nContains age ciphertext and optionally vault.kdbx. Never add decryption keys, plaintext exports or session caches.\n",
    )
    run(["git", "init", "--initial-branch=main", str(bundle)])
    print(
        "Bundle initialized. Back up the age identity offline, separately from the encrypted bundle."
    )


def capture(args, bundle, key):
    config, _ = load_bundle(bundle)
    private_file(key)
    # Capture into a private transaction directory, validate, then replace ciphertext.
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=bundle) as scratch:
        temporary = Path(scratch) / "fnox.toml"
        write_new(temporary, config.read_bytes())
        content = json.dumps(git_identity()).encode()
        put(temporary, key, "IDENTITY", content)
        if args.ssh_key:
            source = outside_public(args.ssh_key)
            private_file(source)
            pub = public_key(source)
            put(temporary, key, "SSH_PRIVATE_KEY", source.read_bytes())
            put(temporary, key, "SSH_PUBLIC_KEY", pub)
        vault = vault_bytes(args.vault_file) if args.vault_file else None
        if vault is not None and (bundle / "vault.kdbx").exists():
            raise RecoveryError("vault.kdbx already exists; update the encrypted vault explicitly")
        # Ensure successful decryption before touching the previous snapshot.
        identity_data(get(temporary, key, "IDENTITY"))
        if vault is not None:
            write_new(bundle / "vault.kdbx", vault)
        try:
            temporary.replace(config)
        except OSError:
            if vault is not None:
                (bundle / "vault.kdbx").unlink()
            raise
    load_bundle(bundle)
    print(
        "Encrypted snapshot updated. Review filenames, scan the bundle, then commit and push it privately."
    )


def update_vault(args, bundle, key):
    _, data = load_bundle(bundle)
    require_recipient(data, key)
    source = outside_public(args.vault_file)
    target = path(bundle / "vault.kdbx")
    if source == target:
        raise RecoveryError("Vault source and bundle destination must be different files")
    if bundle in source.parents:
        raise RecoveryError("Vault source must be outside the recovery bundle")
    if not target.is_file():
        raise RecoveryError("Bundled vault is absent; include it with secrets:capture first")
    incoming = vault_bytes(source)
    previous = vault_bytes(target)
    if incoming == previous:
        print("Vault snapshot already matches the supplied KDBX; no update needed.")
        return

    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    backup_dir = (
        outside_public(args.backup_dir)
        if args.backup_dir
        else path(state / "workstation/vault-backups")
    )
    if backup_dir == bundle or bundle in backup_dir.parents:
        raise RecoveryError("Vault backups must be stored outside the recovery bundle")
    secure_dir(backup_dir)
    backup = path(backup_dir / f"vault-{time.time_ns()}.kdbx")
    write_new(backup, previous)

    temporary = path(bundle / f".vault-update-{time.time_ns()}.tmp")
    try:
        write_new(temporary, incoming)
        vault_bytes(temporary)
        os.replace(temporary, target)
        directory = os.open(bundle, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    print(f"Vault snapshot updated atomically. Previous snapshot: {backup}")
    print(
        "Open the bundle copy, run secrets:check, then commit and refresh every encrypted archive."
    )


def fetch(args, bundle):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", args.repo):
        raise RecoveryError("Use a GitHub OWNER/REPO name")
    if bundle.exists():
        raise RecoveryError(
            "Clone destination already exists; use --bundle or update that checkout explicitly"
        )
    status = subprocess.run(
        ["gh", "auth", "status", "--hostname", "github.com"], capture_output=True
    )
    if status.returncode:
        if not sys.stdin.isatty():
            raise RecoveryError(
                "Run gh auth login interactively before fetching the private bundle"
            )
        subprocess.run(
            ["gh", "auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https"],
            check=True,
        )
    metadata = json.loads(run(["gh", "repo", "view", args.repo, "--json", "isPrivate"]))
    if metadata.get("isPrivate") is not True:
        raise RecoveryError("Recovery source must be a private repository")
    secure_dir(bundle.parent)
    run(["gh", "repo", "clone", f"https://github.com/{args.repo}.git", str(bundle)])
    secure_dir(bundle)


def restore(args, bundle, key):
    if args.repo:
        fetch(args, bundle)
    config, data = load_bundle(bundle)
    private_file(key)
    required = {"IDENTITY"} | ({"SSH_PRIVATE_KEY", "SSH_PUBLIC_KEY"} if args.ssh else set())
    if not required <= set(data["secrets"]):
        raise RecoveryError("Requested recovery data is absent from the bundle")
    home = Path.home()
    identity = path(home / ".config/git/identity.conf")
    ssh = path(os.environ.get("WORKSTATION_SSH_KEY", str(home / ".ssh/id_ed25519")))
    if args.ssh and home / ".ssh" not in ssh.parents:
        raise RecoveryError("SSH destination must be inside ~/.ssh")
    pub = path(str(ssh) + ".pub")
    signers = path(home / ".config/git/allowed_signers")
    vault_target = path(home / ".local/share/keepassxc/vault.kdbx")
    destinations = (
        [identity]
        + ([ssh, pub, signers] if args.ssh else [])
        + ([vault_target] if args.vault else [])
    )
    if any(p.exists() for p in destinations):
        raise RecoveryError(
            "A destination already exists; move it to a private backup before an explicit replacement"
        )
    vault = vault_bytes(bundle / "vault.kdbx") if args.vault else None
    user = identity_data(get(config, key, "IDENTITY"))
    with tempfile.TemporaryDirectory(prefix="workstation-restore-") as scratch:
        private = None
        public = None
        if args.ssh:
            private = get(config, key, "SSH_PRIVATE_KEY")
            candidate = Path(scratch) / "ssh"
            write_new(candidate, private)
            public = public_key(candidate)
            if public != get(config, key, "SSH_PUBLIC_KEY"):
                raise RecoveryError("SSH private/public key mismatch")
        candidate_config = Path(scratch) / "identity"
        write_new(candidate_config, b"")
        settings = {"user.name": user["name"], "user.email": user["email"]}
        if args.ssh:
            settings.update(
                {
                    "user.signingkey": str(pub),
                    "gpg.format": "ssh",
                    "commit.gpgsign": "true",
                    "tag.gpgSign": "true",
                    "gpg.ssh.allowedSignersFile": str(signers),
                }
            )
        for setting, value in settings.items():
            run(["git", "config", "--file", str(candidate_config), setting, value])
        # Validate everything before writing destinations; roll back newly created
        # files if an installation fails. Never replace an existing file.
        outputs = [(identity, candidate_config.read_bytes())]
        if args.ssh:
            outputs.extend(
                [(ssh, private), (pub, public), (signers, user["email"].encode() + b" " + public)]
            )
        if args.vault:
            outputs.append((vault_target, vault))
        created = []
        try:
            for target, content in outputs:
                secure_dir(target.parent)
                write_new(target, content)
                created.append(target)
        except (OSError, RecoveryError):
            for target in created:
                target.unlink()
            raise
    print(
        "Recovery complete. Unlock SSH with sshunlock if restored; sign in to each selected CLI natively."
    )
    if args.vault:
        print("Open ~/.local/share/keepassxc/vault.kdbx with KeePassXC and your master password.")


def check(args, bundle, key):
    config, data = load_bundle(bundle)
    private_file(key)
    if "IDENTITY" not in data["secrets"]:
        raise RecoveryError("Bundle has not been captured yet")
    identity_data(get(config, key, "IDENTITY"))
    ssh_names = {"SSH_PRIVATE_KEY", "SSH_PUBLIC_KEY"}
    if ssh_names & set(data["secrets"]):
        if not ssh_names <= set(data["secrets"]):
            raise RecoveryError("Incomplete SSH key pair in bundle")
        with tempfile.TemporaryDirectory(prefix="workstation-check-") as scratch:
            candidate = Path(scratch) / "ssh"
            write_new(candidate, get(config, key, "SSH_PRIVATE_KEY"))
            if public_key(candidate) != get(config, key, "SSH_PUBLIC_KEY"):
                raise RecoveryError("SSH private/public key mismatch")
    if (bundle / "vault.kdbx").exists():
        vault_bytes(bundle / "vault.kdbx")
    print(
        "Bundle decryption and any SSH pair verified without restoring files or displaying values."
    )
    print(
        "Any KDBX file was checked by header only; unlock it separately with keepassxc-cli to verify its contents."
    )


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "capture", "vault-update", "restore", "check"])
    parser.add_argument("--bundle", default=str(Path.home() / ".local/share/workstation-private"))
    parser.add_argument(
        "--age-key", required=True, help="dedicated age identity, outside every Git repository"
    )
    parser.add_argument("--ssh-key", help="capture only: existing SSH private key to encrypt")
    parser.add_argument("--vault-file", help="capture/vault-update: encrypted .kdbx to include")
    parser.add_argument(
        "--backup-dir", help="vault-update only: private directory for the previous KDBX snapshot"
    )
    parser.add_argument("--repo", help="restore only: clone a private GitHub OWNER/REPO over HTTPS")
    parser.add_argument(
        "--ssh", action="store_true", help="restore only: explicitly restore the SSH key"
    )
    parser.add_argument(
        "--vault",
        action="store_true",
        help="restore only: explicitly restore the KeePassXC database",
    )
    args = parser.parse_args()
    if args.action != "capture" and args.ssh_key:
        parser.error("--ssh-key is only valid for capture")
    if args.action not in ("capture", "vault-update") and args.vault_file:
        parser.error("--vault-file is only valid for capture or vault-update")
    if args.action != "vault-update" and args.backup_dir:
        parser.error("--backup-dir is only valid for vault-update")
    if args.action == "vault-update" and not args.vault_file:
        parser.error("vault-update requires --vault-file")
    if args.action != "restore" and (args.repo or args.ssh or args.vault):
        parser.error("--repo, --ssh and --vault are only valid for restore")
    try:
        bundle, key = outside_public(args.bundle), outside_public(args.age_key)
        if key == bundle or bundle in key.parents:
            raise RecoveryError("Store the age identity separately from the bundle")
        # Refuse a key inside any other Git working tree, including a private one.
        ancestor = key.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        tracked = subprocess.run(
            ["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"], capture_output=True
        )
        if tracked.returncode == 0:
            raise RecoveryError("The age identity cannot live inside a Git working tree")
        functions = {
            "init": initialize,
            "capture": capture,
            "vault-update": update_vault,
            "restore": restore,
            "check": check,
        }
        functions[args.action](args, bundle, key)
    except (RecoveryError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        # Keep explicit safe diagnostics; never echo malformed payloads or command output.
        error = sys.exc_info()[1]
        message = (
            str(error)
            if isinstance(error, RecoveryError)
            else "Recovery failed: verify files, permissions and tool availability"
        )
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
