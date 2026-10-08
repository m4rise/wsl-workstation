"""Test the Codex Agent Host symlink with a disposable fake CLI."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/codex-agent-host.sh"
SUFFIX = ".local/share/vscode-codex-sdk/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"


class CodexAgentHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.cli = self.home / ".local/bin/codex"
        self.agent = self.home / SUFFIX
        self.env = dict(os.environ, HOME=str(self.home))

    def install_cli(self, version):
        release = self.home / ".codex/releases" / version / "codex"
        release.parent.mkdir(parents=True, exist_ok=True)
        release.write_text(f"#!/bin/sh\necho codex-cli {version}\n")
        release.chmod(0o755)
        self.cli.parent.mkdir(parents=True, exist_ok=True)
        self.cli.unlink(missing_ok=True)
        self.cli.symlink_to(release)

    def run_task(self, mode="ensure"):
        return subprocess.run(
            ["bash", str(SCRIPT), mode], env=self.env, capture_output=True, text=True
        )

    def test_idempotent_and_upgrade_follows_stable_cli_path(self):
        self.install_cli("0.161.0")
        self.assertNotEqual(self.run_task("check").returncode, 0)
        for _ in range(2):
            self.assertEqual(self.run_task().returncode, 0)
        self.assertEqual(self.agent.readlink(), self.cli)
        self.install_cli("0.162.0")
        result = self.run_task("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.162.0", result.stdout)

    def test_refuses_collision(self):
        self.install_cli("0.161.0")
        self.agent.parent.mkdir(parents=True)
        self.agent.write_text("unrelated")
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertEqual(self.agent.read_text(), "unrelated")

    def test_missing_cli_does_not_provision(self):
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertFalse(self.agent.exists())


if __name__ == "__main__":
    unittest.main()
