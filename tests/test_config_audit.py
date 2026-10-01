"""Summarize native state without disclosing rendered contents or personal values."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "config_audit", Path(__file__).resolve().parents[1] / "scripts/config-audit.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class ConfigAuditTests(unittest.TestCase):
    def test_native_status_reports_drift_and_unknown_without_contents(self):
        home = Path("/home") / "fixture-owner"
        secret = "disposable-private-content"
        data = {
            "files": [
                {
                    "id": {"name": str(home / ".ssh/config")},
                    "action": "update",
                    "current": secret,
                    "desired": secret,
                }
            ],
            "services": [{"id": {"name": "fixture.timer"}, "action": "unknown", "current": secret}],
            "dotfiles": {"files": [{"target": "~/.zshrc", "state": "conflict"}]},
            "repos": [{"path_raw": "~/.oh-my-zsh", "state": "dirty", "reason": secret}],
            "tools": [{"tool": "ruff", "installed": False}],
        }
        rows = audit.issues(data, home)
        self.assertEqual(len(rows), 5)
        self.assertNotIn(secret, str(rows))
        self.assertNotIn(str(home), str(rows))
        self.assertIn(("UNKNOWN", "fixture.timer", "services"), rows)

    def test_healthy_state_is_quiet_and_unknown_native_categories_still_fail_check(self):
        result = subprocess.CompletedProcess(
            [],
            0,
            json.dumps(
                {"files": [{"action": "noop"}], "dotfiles": {"files": [{"state": "applied"}]}}
            ),
            "",
        )
        output = io.StringIO()
        with (
            mock.patch.object(audit.subprocess, "run", return_value=result),
            mock.patch("sys.argv", ["audit", "--check"]),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(audit.main(), 0)
        self.assertEqual(
            output.getvalue().strip(), "Managed configuration is in its desired state."
        )
        result.returncode = 1
        result.stdout = json.dumps({"future_resource": {"action": "update"}})
        with (
            mock.patch.object(audit.subprocess, "run", return_value=result),
            mock.patch("sys.argv", ["audit", "--check"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(audit.main(), 1)

    def test_native_failure_does_not_print_raw_output(self):
        result = subprocess.CompletedProcess(
            [], 2, "disposable-private-value", "disposable-private-value"
        )
        output = io.StringIO()
        with (
            mock.patch.object(audit.subprocess, "run", return_value=result),
            mock.patch("sys.argv", ["audit"]),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(audit.main(), 2)
        self.assertNotIn("disposable-private-value", output.getvalue())

    def test_inventory_does_not_follow_git_includes_or_change_files(self):
        with tempfile.TemporaryDirectory(prefix="workstation-inventory-") as directory:
            home = Path(directory)
            included = home / "included"
            included.write_text("[pull]\nrebase = true\n")
            config = home / ".gitconfig"
            config.write_text(
                f"[include]\npath = {included}\n[user]\nname = disposable-private-value\n[rerere]\nenabled = true\n"
            )
            before = config.read_bytes()
            report = str(audit.inventory(home, home))
            self.assertNotIn("disposable-private-value", report)
            self.assertNotIn(str(included), report)
            self.assertIn("rerere", report)
            self.assertNotIn("pull", report)
            self.assertEqual(before, config.read_bytes())

    def test_real_native_status_for_isolated_missing_dotfile(self):
        with tempfile.TemporaryDirectory(prefix="workstation-native-audit-") as directory:
            root = Path(directory)
            target = root / "missing-dotfile"
            (root / "config.toml").write_text(
                f'[dotfiles]\n"{target}" = {{ source = "fixture", mode = "symlink" }}\n'
            )
            (root / "fixture").write_text("fixture\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith("MISE_")}
            env.update(
                MISE_CONFIG_DIR=str(root),
                MISE_GLOBAL_CONFIG_ROOT=str(root),
                MISE_SYSTEM_CONFIG_DIR=str(root / "system"),
                MISE_STATE_DIR=str(root / "state"),
                MISE_CACHE_DIR=str(root / "cache"),
                MISE_TRUSTED_CONFIG_PATHS=str(root),
            )
            result = subprocess.run(
                ["mise", "bootstrap", "status", "--missing", "--json"],
                env=env,
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(audit.issues(json.loads(result.stdout), root))


if __name__ == "__main__":
    unittest.main()
