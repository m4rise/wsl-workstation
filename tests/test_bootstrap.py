"""Verify installer integrity and preserve a supported workstation installation."""

import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    import bootstrap_metadata

    SPEC = importlib.util.spec_from_file_location("install_mise", SCRIPTS / "install-mise.py")
    installer = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(installer)
finally:
    sys.path.pop(0)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workstation-installer-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "system/bootstrap").mkdir(parents=True)
        (self.root / "config.toml").write_text('min_version = "2026.9.13"\n')
        self.content = b"#!/bin/sh\nexit 0\n"
        self.data = {
            "version": "2026.9.13",
            "installer_sha256": hashlib.sha256(self.content).hexdigest(),
        }
        self.write_metadata()

    def write_metadata(self):
        (self.root / "system/bootstrap/mise.json").write_text(json.dumps(self.data))

    def invoke(self):
        with (
            mock.patch.object(installer, "ROOT", self.root),
            mock.patch.object(installer, "load_metadata", return_value=self.data),
            mock.patch.object(installer.Path, "home", return_value=self.root),
            mock.patch("sys.argv", ["install-mise"]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return installer.main()

    def test_metadata_rejects_version_below_minimum_and_malformed_digest(self):
        self.assertEqual(bootstrap_metadata.load_metadata(self.root), self.data)
        self.data["version"] = "2026.9.12"
        self.write_metadata()
        with self.assertRaises(ValueError):
            bootstrap_metadata.load_metadata(self.root)
        self.data.update(version="2026.9.13", installer_sha256="invalid")
        self.write_metadata()
        with self.assertRaises(ValueError):
            bootstrap_metadata.load_metadata(self.root)

    def test_supported_existing_mise_is_not_downloaded_or_replaced(self):
        binary = self.root / ".local/bin/mise"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"supported-existing-binary")
        binary.chmod(0o755)
        result = subprocess.CompletedProcess([], 0, "2026.9.18 linux-x64\n", "")
        with (
            mock.patch.object(installer.subprocess, "run", return_value=result),
            mock.patch.object(installer.urllib.request, "urlopen") as download,
        ):
            self.assertEqual(self.invoke(), 0)
        download.assert_not_called()
        self.assertEqual(binary.read_bytes(), b"supported-existing-binary")

    def test_mismatched_installer_is_never_executed(self):
        with (
            mock.patch.object(installer.urllib.request, "urlopen") as download,
            mock.patch.object(installer.subprocess, "run") as execute,
        ):
            download.return_value.__enter__.return_value.read.return_value = b"tampered"
            self.assertEqual(self.invoke(), 1)
        execute.assert_not_called()

    def test_verified_installer_uses_shared_pinned_version(self):
        with (
            mock.patch.object(installer.urllib.request, "urlopen") as download,
            mock.patch.object(installer.subprocess, "run") as execute,
        ):
            download.return_value.__enter__.return_value.read.return_value = self.content
            self.assertEqual(self.invoke(), 0)
        environment = execute.call_args.kwargs["env"]
        self.assertEqual(environment["MISE_VERSION"], self.data["version"])
        self.assertEqual(environment["MISE_INSTALL_PATH"], str(self.root / ".local/bin/mise"))


if __name__ == "__main__":
    unittest.main()
