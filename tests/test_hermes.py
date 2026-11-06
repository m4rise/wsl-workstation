"""Release integrity, non-destructive provisioning and quarantined recovery."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hermes", ROOT / "scripts/hermes.py")
hermes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hermes)


class HermesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="workstation-hermes-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.release = self.root / "releases/0.2.0"
        self.archive = self.root / "hermes-runner-linux-0.2.0.tar.gz"
        self.expected = json.loads((ROOT / "system/hermes/release.json").read_text())
        self.lock = {
            "revision": self.expected["hermes_revision"],
            "sha256": self.expected["hermes_sha256"],
            "patches": [],
        }
        with tarfile.open(self.archive, "w:gz") as archive:
            self.member(
                archive,
                "hermes-runner-linux-0.2.0/vendor/hermes-lock.json",
                json.dumps(self.lock).encode(),
            )
            self.member(archive, "hermes-runner-linux-0.2.0/tools/install.py", b"# fixture")
        self.expected["sha256"] = hermes.digest(self.archive)
        patch = mock.patch.object(hermes, "metadata", return_value=self.expected)
        patch.start()
        self.addCleanup(patch.stop)
        self.args = argparse.Namespace(archive=str(self.archive), destination=str(self.release))

    @staticmethod
    def member(archive, name, content):
        info = tarfile.TarInfo(name)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))

    def fake_installer(self, arguments, **_kwargs):
        destination = Path(arguments[-1])
        (destination / "component/bin").mkdir(parents=True)
        (destination / "component/bin/hrl").write_text("fixture installed component")
        (destination / ".hrl-install.json").write_text(
            json.dumps(
                {
                    "component": "0.2.0",
                    "hermes": self.lock,
                }
            )
        )

    def install(self):
        with (
            mock.patch.object(
                hermes, "prerequisites", return_value=(Path("python"), Path("codex"))
            ),
            mock.patch.object(hermes.subprocess, "run", side_effect=self.fake_installer) as execute,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            hermes.install(self.args)
        return execute

    def test_second_provision_preserves_component_and_never_rebuilds(self):
        self.assertEqual(self.install().call_count, 1)
        receipt = self.release / hermes.RECEIPT
        before = (receipt.read_bytes(), receipt.stat().st_mtime_ns)
        with (
            mock.patch.object(hermes, "prerequisites") as prerequisites,
            mock.patch.object(hermes.subprocess, "run") as execute,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            hermes.install(self.args)
        prerequisites.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(before, (receipt.read_bytes(), receipt.stat().st_mtime_ns))
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    def test_mismatch_refuses_before_any_execution(self):
        self.archive.write_bytes(b"changed")
        with mock.patch.object(hermes.subprocess, "run") as execute:
            with self.assertRaisesRegex(ValueError, "SHA256"):
                hermes.install(self.args)
            execute.assert_not_called()
        self.assertFalse(self.release.exists())

    def test_installed_changes_are_not_overwritten(self):
        self.install()
        binary = self.release / "component/bin/hrl"
        binary.write_text("changed by operator")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.install()
        self.assertEqual(binary.read_text(), "changed by operator")

    def test_existing_unowned_destination_and_symlink_are_refused(self):
        self.release.mkdir(parents=True)
        (self.release / "user-state").write_text("preserve")
        with self.assertRaises(FileNotFoundError):
            self.install()
        self.assertEqual((self.release / "user-state").read_text(), "preserve")
        alias = self.root / "alias"
        alias.symlink_to(self.release, target_is_directory=True)
        self.args.destination = str(alias)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.install()

    def test_bytecode_added_after_install_is_detected(self):
        self.install()
        bytecode = self.release / "component/src/__pycache__/module.pyc"
        bytecode.parent.mkdir(parents=True)
        bytecode.write_bytes(b"untrusted bytecode")
        with self.assertRaisesRegex(ValueError, "integrity"):
            hermes.installed(self.release)

    def test_configuration_cannot_place_data_inside_install_via_dotdot(self):
        self.install()
        args = argparse.Namespace(
            installation=str(self.release),
            config=str(self.root / "project.json"),
            data=str(self.root / "outside/../releases/0.2.0/data"),
        )
        with self.assertRaisesRegex(ValueError, "outside the installation"):
            hermes.configure(args)
        self.assertFalse((self.root / "project.json").exists())

    def test_uninstall_requires_config_for_selected_release(self):
        self.install()
        config = self.root / "other.json"
        config.write_text(json.dumps({"hermes": str(self.root / "other-release/hermes")}))
        with (
            mock.patch.dict(os.environ, {"WORKSTATION_HERMES": "1"}),
            mock.patch(
                "sys.argv",
                [
                    "hermes",
                    "uninstall",
                    "--installation",
                    str(self.release),
                    "--config",
                    str(config),
                ],
            ),
            mock.patch.object(hermes.subprocess, "run") as execute,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(hermes.main(), 1)
        execute.assert_not_called()
        self.assertTrue(self.release.exists())

    def test_restore_is_private_quarantine_and_cannot_overwrite(self):
        backup = self.root / "backup.tar.gz"
        active = self.root / "active"
        active.mkdir()
        (active / "revoked").write_text("newer revocation")
        with tarfile.open(backup, "w:gz") as archive:
            self.member(archive, "config.json", json.dumps({"data": str(active)}).encode())
            directory = tarfile.TarInfo("data")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            self.member(archive, "data/skill", b"old knowledge")
            link = tarfile.TarInfo("data/internal-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "skill"
            archive.addfile(link)
            link = tarfile.TarInfo("data/hard-link")
            link.type = tarfile.LNKTYPE
            link.linkname = "data/skill"
            archive.addfile(link)
        destination = self.root / "quarantine"
        args = argparse.Namespace(backup=str(backup), destination=str(destination))
        with contextlib.redirect_stdout(io.StringIO()):
            hermes.restore(args)
        self.assertFalse((destination / "config.json").exists())
        self.assertFalse(
            json.loads((destination / "RESTORE-REVIEW-REQUIRED.json").read_text())["activated"]
        )
        self.assertEqual((destination / "data/skill").stat().st_mode & 0o777, 0o600)
        self.assertEqual((destination / "data/internal-link").read_bytes(), b"old knowledge")
        self.assertTrue((destination / "data/internal-link").is_symlink())
        self.assertEqual((destination / "data/hard-link").read_bytes(), b"old knowledge")
        self.assertEqual((active / "revoked").read_text(), "newer revocation")
        self.assertFalse((active / "skill").exists())
        with self.assertRaisesRegex(ValueError, "exists"):
            hermes.restore(args)

    def test_archive_traversal_and_links_are_rejected_before_extraction(self):
        for name, kind in (("../escaped", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            with self.subTest(name=name):
                archive = self.root / "unsafe.tar.gz"
                with tarfile.open(archive, "w:gz") as target:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    info.linkname = "/tmp"
                    target.addfile(info)
                destination = self.root / "extract"
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    hermes.extract(archive, destination)
                self.assertFalse(destination.exists())

    def test_quarantine_rejects_links_outside_destination(self):
        archive = self.root / "external-link.tar.gz"
        with tarfile.open(archive, "w:gz") as target:
            info = tarfile.TarInfo("data/external")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside"
            target.addfile(info)
        with self.assertRaises(tarfile.FilterError):
            hermes.extract(archive, self.root / "extract", safe_links=True)

    def test_capability_must_be_explicit(self):
        with (
            mock.patch.dict(os.environ, {"WORKSTATION_HERMES": "0"}),
            mock.patch("sys.argv", ["hermes", "dependencies"]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            hermes.main()

    def test_pinned_tools_are_scoped_to_task_children(self):
        binary = self.root / "pinned/bin/codex"
        binary.parent.mkdir(parents=True)
        binary.touch()
        with mock.patch.object(hermes.subprocess, "check_output", return_value=str(binary)) as call:
            self.assertEqual(hermes.tool("codex"), binary)
        self.assertEqual(
            call.call_args.args[0],
            ["mise", "-E", "hermes-tools", "which", "codex", "--tool", "aqua:openai/codex@0.166.0"],
        )
        with (
            mock.patch.object(hermes, "tool", return_value=binary),
            mock.patch.dict(os.environ, PATH="/standalone/bin:/usr/bin"),
        ):
            env = hermes.tool_environment()
            self.assertEqual(env["PATH"], str(binary.parent) + ":/standalone/bin:/usr/bin")
            self.assertEqual(os.environ["PATH"], "/standalone/bin:/usr/bin")

    def test_fetch_uses_versioned_asset_and_checks_before_retaining(self):
        destination = self.root / "download.tar.gz"
        args = argparse.Namespace(repository="example/hrl", destination=str(destination))

        def download(argv, **_kwargs):
            (Path(argv[-1]) / self.expected["archive"]).write_bytes(self.archive.read_bytes())

        with (
            mock.patch.object(hermes, "tool", return_value=Path("/pinned/gh")),
            mock.patch.object(hermes.subprocess, "run", side_effect=download) as call,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with mock.patch.object(hermes, "digest", return_value="wrong"):
                with self.assertRaisesRegex(ValueError, "Downloaded distribution SHA256"):
                    hermes.fetch(args)
            self.assertFalse(destination.exists())
            hermes.fetch(args)
            argv = call.call_args.args[0]
            self.assertEqual(argv[:4], ["/pinned/gh", "release", "download", "v0.2.0"])
            self.assertEqual(
                argv[4:8], ["--repo", "example/hrl", "--pattern", self.expected["archive"]]
            )
            self.assertEqual(destination.read_bytes(), self.archive.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            call.reset_mock()
            hermes.fetch(args)
            call.assert_not_called()
            destination.write_bytes(b"operator file")
            with self.assertRaisesRegex(ValueError, "Existing archive SHA256"):
                hermes.fetch(args)
            self.assertEqual(destination.read_bytes(), b"operator file")


if __name__ == "__main__":
    unittest.main()
