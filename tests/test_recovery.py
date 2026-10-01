"""Real age/fnox/OpenSSH round trips; all credentials are disposable fixtures."""

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recovery", ROOT / "scripts/secrets.py")
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workstation-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bundle = self.root / "bundle"
        self.key = self.root / "age.txt"
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.home),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"),
            GIT_CONFIG_NOSYSTEM="1",
            WORKSTATION_SSH_KEY=str(self.home / ".ssh/id_ed25519"),
        )
        for k in list(self.env):
            if (
                k.startswith("FNOX_")
                or k.startswith("GIT_CONFIG_KEY_")
                or k.startswith("GIT_CONFIG_VALUE_")
            ):
                self.env.pop(k)
        self.env.pop("GIT_CONFIG_COUNT", None)
        for setting, value in [
            ("user.name", "Recovery Test"),
            ("user.email", "restore@example.invalid"),
        ]:
            self.tool("git", "config", "--global", setting, value)
        self.call("init")
        self.ssh = self.root / "source-key"
        self.tool(
            "ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "fixture", "-f", str(self.ssh)
        )

    def tool(self, *command, **kwargs):
        result = subprocess.run(
            command, env=kwargs.pop("env", self.env), capture_output=True, **kwargs
        )
        self.assertEqual(result.returncode, 0, f"Fixture tool failed: {command[0]}")
        return result.stdout

    def call(self, action, *arguments, ok=True, key=None, cwd=None):
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/secrets.py"),
                action,
                "--bundle",
                str(self.bundle),
                "--age-key",
                str(key or self.key),
                *arguments,
            ],
            env=self.env,
            cwd=cwd,
            capture_output=True,
        )
        output = result.stdout + result.stderr
        self.assertNotIn(b"restore@example.invalid", output)
        self.assertNotIn(b"BEGIN OPENSSH PRIVATE KEY", output)
        self.assertNotIn(b"AGE-SECRET-KEY-", output)
        self.assertEqual(result.returncode == 0, ok, output.decode(errors="replace"))
        return result

    def capture(self):
        self.call("capture", "--ssh-key", str(self.ssh))

    def test_round_trip_identity_and_ssh(self):
        self.capture()
        self.call("check")
        # Hostile inherited provider overrides must not change the recovery key.
        self.env["FNOX_AGE_KEY"] = "invalid-inherited-key"
        self.call("restore", "--ssh")
        restored = self.home / ".ssh/id_ed25519"
        self.assertEqual(restored.read_bytes(), self.ssh.read_bytes())
        self.assertEqual(
            self.tool("ssh-keygen", "-y", "-f", str(restored)),
            self.tool("ssh-keygen", "-y", "-f", str(self.ssh)),
        )
        self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(restored.parent.stat().st_mode), 0o700)
        identity = self.home / ".config/git/identity.conf"
        self.assertEqual(stat.S_IMODE(identity.stat().st_mode), 0o600)
        self.assertEqual(
            self.tool("git", "config", "--file", str(identity), "user.email").strip(),
            b"restore@example.invalid",
        )
        # Verify that the restored identity really signs and verifies a commit.
        self.tool("git", "config", "--global", "include.path", str(identity))
        checkout = self.root / "signed-repo"
        self.tool("git", "init", str(checkout))
        self.tool(
            "git", "-C", str(checkout), "commit", "--allow-empty", "-m", "test: restored signing"
        )
        self.tool("git", "-C", str(checkout), "verify-commit", "HEAD")

    def test_identity_only_does_not_restore_ssh_or_enable_signing(self):
        self.capture()
        self.call("restore")
        self.assertFalse((self.home / ".ssh/id_ed25519").exists())
        self.assertNotIn("gpgsign", (self.home / ".config/git/identity.conf").read_text().lower())

    def test_capture_reads_included_git_identity(self):
        identity = self.root / "included.conf"
        self.tool("git", "config", "--file", str(identity), "user.name", "Included Identity")
        self.tool(
            "git", "config", "--file", str(identity), "user.email", "included@example.invalid"
        )
        self.tool("git", "config", "--global", "--unset", "user.name")
        self.tool("git", "config", "--global", "--unset", "user.email")
        self.tool("git", "config", "--global", "include.path", str(identity))
        self.call("capture")
        self.call("restore")
        restored = self.home / ".config/git/identity.conf"
        self.assertEqual(
            self.tool("git", "config", "--file", str(restored), "user.email").strip(),
            b"included@example.invalid",
        )

    def test_repository_identity_cannot_replace_user_identity(self):
        checkout = self.root / "local-repo"
        self.tool("git", "init", str(checkout))
        self.tool("git", "-C", str(checkout), "config", "user.name", "Repository Identity")
        self.tool("git", "-C", str(checkout), "config", "user.email", "repository@example.invalid")
        self.call("capture", cwd=checkout)
        self.call("restore")
        restored = self.home / ".config/git/identity.conf"
        self.assertEqual(
            self.tool("git", "config", "--file", str(restored), "user.email").strip(),
            b"restore@example.invalid",
        )

    def test_existing_key_is_never_overwritten(self):
        self.capture()
        target = self.home / ".ssh/id_ed25519"
        target.parent.mkdir()
        target.write_bytes(b"existing-key")
        self.call("restore", "--ssh", ok=False)
        self.assertEqual(target.read_bytes(), b"existing-key")
        self.assertFalse((self.home / ".config/git/identity.conf").exists())

    def test_absent_bundle_and_missing_data(self):
        shutil.rmtree(self.bundle)
        self.call("restore", ok=False)
        self.call("init")
        self.call("restore", "--ssh", ok=False)

    def test_missing_or_wrong_age_key(self):
        self.capture()
        wrong = self.root / "wrong-age.txt"
        self.tool("age-keygen", "-o", str(wrong))
        wrong.chmod(0o600)
        self.call("restore", key=wrong, ok=False)
        self.call("restore", key=self.root / "absent.txt", ok=False)
        self.assertFalse((self.home / ".config/git/identity.conf").exists())

    def test_insecure_key_permissions(self):
        self.capture()
        for mode in (0o644, 0o700):
            self.key.chmod(mode)
            self.call("restore", ok=False)

    def test_failed_write_removes_incomplete_private_file(self):
        target = self.root / "partial-key"
        with mock.patch.object(recovery.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                recovery.write_new(target, b"disposable-private-data")
        self.assertFalse(target.exists())

    def test_vault_write_failure_preserves_previous_snapshot(self):
        self.capture()
        config = self.bundle / "fnox.toml"
        previous = config.read_bytes()
        vault = self.root / "fixture.kdbx"
        vault.write_bytes(recovery.KDBX + b"header-only-fixture")
        original = recovery.write_new

        def failing_write(target, content):
            if target == self.bundle / "vault.kdbx":
                raise OSError("disk failure")
            return original(target, content)

        args = type("Args", (), {"ssh_key": None, "vault_file": str(vault)})()
        with (
            mock.patch.dict(os.environ, self.env, clear=True),
            mock.patch.object(recovery, "write_new", side_effect=failing_write),
        ):
            with self.assertRaises(OSError):
                recovery.capture(args, self.bundle, self.key)
        self.assertEqual(config.read_bytes(), previous)

    def test_additional_age_recipient_is_rejected(self):
        self.capture()
        extra = self.root / "extra-age.txt"
        self.tool("age-keygen", "-o", str(extra))
        recipient = self.tool("age-keygen", "-y", str(extra)).decode().strip()
        config = self.bundle / "fnox.toml"
        content = config.read_text().replace(
            "recipients = [", "recipients = [" + json.dumps(recipient) + ", "
        )
        config.write_text(content)
        self.call("capture", ok=False)
        self.assertEqual(config.read_text(), content)

    def test_fnox_executes_validated_snapshot(self):
        self.capture()
        config = self.bundle / "fnox.toml"
        original = recovery.run

        def mutate_source(command, **kwargs):
            if command[0] == "fnox":
                config.write_text('import = ["/untrusted.toml"]\n' + config.read_text())
                self.assertNotEqual(Path(command[2]), config)
            return original(command, **kwargs)

        with (
            mock.patch.dict(os.environ, self.env, clear=True),
            mock.patch.object(recovery, "run", side_effect=mutate_source),
        ):
            value = recovery.get(config, self.key, "IDENTITY")
        self.assertEqual(json.loads(value)["email"], "restore@example.invalid")

    def test_missing_vault_and_mismatched_ssh_are_atomic(self):
        self.capture()
        self.call("restore", "--vault", ok=False)
        self.assertFalse((self.home / ".config/git/identity.conf").exists())
        # Swap a ciphertext field without exposing or faking the encryption.
        config = self.bundle / "fnox.toml"
        text = (
            config.read_text()
            .replace("SSH_PUBLIC_KEY", "TMP")
            .replace("SSH_PRIVATE_KEY", "SSH_PUBLIC_KEY")
            .replace("TMP", "SSH_PRIVATE_KEY")
        )
        config.write_text(text)
        self.call("check", ok=False)
        self.call("restore", "--ssh", ok=False)
        self.assertFalse((self.home / ".ssh/id_ed25519").exists())

    def test_symlink_destinations_and_key_in_bundle_are_rejected(self):
        self.capture()
        target = self.home / ".ssh"
        target.symlink_to(self.root, target_is_directory=True)
        self.call("restore", "--ssh", ok=False)
        self.call("restore", key=self.bundle / "age.txt", ok=False)

    def test_active_fnox_configuration_is_rejected(self):
        self.capture()
        config = self.bundle / "fnox.toml"
        config.write_text('import = ["/tmp/untrusted.toml"]\n' + config.read_text())
        self.call("restore", ok=False)

    def test_vault_round_trip(self):
        # fnox can create a real KDBX fixture; recovery itself never unlocks it.
        fixture = self.root / "fixture.toml"
        vault = self.root / "source.kdbx"
        fixture.write_text(
            '[providers.test]\ntype = "keepass"\ndatabase = ' + json.dumps(str(vault)) + "\n"
        )
        env = self.env.copy()
        env.update(
            FNOX_CONFIG_DIR=str(self.root / "empty-config"),
            FNOX_KEEPASS_PASSWORD="disposable-test-password",
        )
        self.tool(
            "fnox",
            "--config",
            str(fixture),
            "set",
            "FIXTURE",
            "--provider",
            "test",
            env=env,
            input=b"disposable-value",
        )
        self.call("capture", "--vault-file", str(vault))
        self.call("restore", "--vault")
        restored = self.home / ".local/share/keepassxc/vault.kdbx"
        self.assertEqual(restored.read_bytes(), vault.read_bytes())
        # Read the restored database with the real provider, proving it is usable.
        fixture.write_text(fixture.read_text().replace(str(vault), str(restored)))
        self.assertEqual(
            self.tool("fnox", "--config", str(fixture), "get", "FIXTURE", env=env).strip(),
            b"disposable-value",
        )
        self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o600)

    def test_vault_update_is_atomic_backed_up_and_idempotent(self):
        fixture = self.root / "update-fixture.toml"
        first = self.root / "first.kdbx"
        second = self.root / "second.kdbx"
        env = self.env.copy()
        env.update(
            FNOX_CONFIG_DIR=str(self.root / "empty-config"),
            FNOX_KEEPASS_PASSWORD="disposable-test-password",
        )
        for vault, value in ((first, "first-value"), (second, "second-value")):
            fixture.write_text(
                '[providers.test]\ntype = "keepass"\ndatabase = ' + json.dumps(str(vault)) + "\n"
            )
            self.tool(
                "fnox",
                "--config",
                str(fixture),
                "set",
                "FIXTURE",
                "--provider",
                "test",
                env=env,
                input=value.encode(),
            )

        self.call("capture", "--vault-file", str(first))
        self.call("vault-update", "--vault-file", str(second))
        bundled = self.bundle / "vault.kdbx"
        self.assertEqual(bundled.read_bytes(), second.read_bytes())
        backups = list((self.home / ".local/state/workstation/vault-backups").glob("vault-*.kdbx"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), first.read_bytes())
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(backups[0].parent.stat().st_mode), 0o700)

        # Reapplying identical bytes creates no unnecessary backup.
        self.call("vault-update", "--vault-file", str(second))
        self.assertEqual(len(list(backups[0].parent.glob("vault-*.kdbx"))), 1)

        invalid = self.root / "invalid.kdbx"
        invalid.write_bytes(b"not-a-kdbx")
        self.call("vault-update", "--vault-file", str(invalid), ok=False)
        self.assertEqual(bundled.read_bytes(), second.read_bytes())
        wrong = self.root / "wrong-update-age.txt"
        self.tool("age-keygen", "-o", str(wrong))
        wrong.chmod(0o600)
        self.call("vault-update", "--vault-file", str(first), key=wrong, ok=False)
        self.assertEqual(bundled.read_bytes(), second.read_bytes())

        self.call("restore", "--vault")
        self.assertEqual(
            (self.home / ".local/share/keepassxc/vault.kdbx").read_bytes(), second.read_bytes()
        )

    def test_vault_update_replace_failure_preserves_previous_snapshot(self):
        first = self.root / "first.kdbx"
        second = self.root / "second.kdbx"
        first.write_bytes(recovery.KDBX + b"first-valid-header")
        second.write_bytes(recovery.KDBX + b"second-valid-header")
        self.call("capture", "--vault-file", str(first))
        target = self.bundle / "vault.kdbx"
        args = type("Args", (), {"vault_file": str(second), "backup_dir": None})()
        with (
            mock.patch.dict(os.environ, self.env, clear=True),
            mock.patch.object(recovery.os, "replace", side_effect=OSError("disk failure")),
        ):
            with self.assertRaises(OSError):
                recovery.update_vault(args, self.bundle, self.key)
        self.assertEqual(target.read_bytes(), first.read_bytes())
        self.assertFalse(list(self.bundle.glob(".vault-update-*.tmp")))
        backups = list((self.home / ".local/state/workstation/vault-backups").glob("vault-*.kdbx"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), first.read_bytes())

    def test_keepassxc_without_display(self):
        if not shutil.which("keepassxc-cli"):
            if os.environ.get("WORKSTATION_VAULT") == "1":
                self.fail("vault selected but keepassxc-cli is missing")
            self.skipTest("keepassxc-cli absent; required in the WSL personal bootstrap job")
        env = self.env.copy()
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM"):
            env.pop(key, None)
        password = b"disposable-master-passphrase\n"
        vault = self.root / "headless.kdbx"
        self.tool(
            "keepassxc-cli", "db-create", "--set-password", str(vault), env=env, input=password * 2
        )
        self.tool(
            "keepassxc-cli",
            "add",
            "--password-prompt",
            str(vault),
            "fixture",
            env=env,
            input=password + b"disposable-entry-password\n",
        )
        self.call("capture", "--vault-file", str(vault))
        self.call("restore", "--vault")
        restored = self.home / ".local/share/keepassxc/vault.kdbx"
        value = self.tool(
            "keepassxc-cli",
            "show",
            "--attributes",
            "Password",
            str(restored),
            "fixture",
            env=env,
            input=password,
        )
        self.assertEqual(value.strip(), b"disposable-entry-password")
        wrong = subprocess.run(
            ["keepassxc-cli", "db-info", str(restored)],
            env=env,
            input=b"wrong-password\n",
            capture_output=True,
        )
        self.assertNotEqual(wrong.returncode, 0)

    def test_capture_contains_only_ciphertext(self):
        self.capture()
        data = (self.bundle / "fnox.toml").read_bytes()
        for value in [b"restore@example.invalid", b"Recovery Test", self.ssh.read_bytes()]:
            self.assertNotIn(value, data)


if __name__ == "__main__":
    unittest.main()
