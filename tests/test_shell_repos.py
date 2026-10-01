"""Exercise snapshot maintenance using disposable Git repositories without network."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "shell_repos", Path(__file__).resolve().parents[1] / "scripts/shell-repos.py"
)
shell = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shell)


class ShellReposTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workstation-shell-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.run_git(self.origin, "init", "--initial-branch=main")
        (self.origin / "fixture").write_text("initial\n")
        self.run_git(self.origin, "add", ".")
        self.commit("initial")
        self.pin = shell.git(self.origin, "rev-parse", "HEAD")
        self.repo = self.home / "shell"
        self.repo.parent.mkdir()
        self.run_git(self.root, "clone", str(self.origin), str(self.repo))
        self.write_snapshot()

    def run_git(self, directory, *args):
        subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True)

    def commit(self, message):
        self.run_git(
            self.origin,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-am",
            message,
        )

    def write_snapshot(self):
        self.snapshot = self.root / "config.reproducible.toml"
        self.snapshot.write_text(
            f'[bootstrap.repos]\n"~/shell" = {{ url = {json.dumps(str(self.origin))}, ref = "{self.pin}" }}\n'
        )

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            shell.prepare_update(self.root, self.home)

    def test_pinned_clean_repository_resumes_default_branch_for_updates(self):
        self.run_git(self.repo, "checkout", "--detach", self.pin)
        self.prepare()
        self.assertEqual(shell.git(self.repo, "branch", "--show-current"), "main")
        (self.origin / "fixture").write_text("upstream update\n")
        self.commit("update")
        self.run_git(self.repo, "pull", "--ff-only")
        self.assertEqual((self.repo / "fixture").read_text(), "upstream update\n")

    def test_dirty_and_unrecognized_detached_repositories_are_preserved(self):
        self.run_git(self.repo, "checkout", "--detach", self.pin)
        (self.repo / "fixture").write_text("local change\n")
        self.prepare()
        self.assertEqual(shell.git(self.repo, "branch", "--show-current"), "")
        self.assertEqual((self.repo / "fixture").read_text(), "local change\n")
        self.run_git(self.repo, "restore", "fixture")
        self.pin = "0" * 40
        self.write_snapshot()
        self.prepare()
        self.assertEqual(shell.git(self.repo, "branch", "--show-current"), "")

    def test_fresh_clone_with_newer_default_branch_can_resume_from_old_snapshot(self):
        (self.origin / "fixture").write_text("newer upstream\n")
        self.commit("newer")
        self.run_git(self.repo, "pull", "--ff-only")
        self.run_git(self.repo, "checkout", "--detach", self.pin)
        self.prepare()
        self.assertEqual(shell.git(self.repo, "branch", "--show-current"), "main")
        self.assertEqual((self.repo / "fixture").read_text(), "newer upstream\n")

    def test_existing_branch_is_not_changed(self):
        self.run_git(self.repo, "switch", "-c", "local-work")
        self.prepare()
        self.assertEqual(shell.git(self.repo, "branch", "--show-current"), "local-work")

    def test_snapshot_is_atomic_and_refuses_dirty_repositories(self):
        before = self.snapshot.read_bytes()
        (self.repo / "fixture").write_text("local change\n")
        with self.assertRaises(ValueError):
            shell.freeze(self.root, self.home)
        self.assertEqual(before, self.snapshot.read_bytes())
        self.run_git(self.repo, "restore", "fixture")
        (self.origin / "fixture").write_text("new snapshot\n")
        self.commit("snapshot")
        self.run_git(self.repo, "pull", "--ff-only")
        with contextlib.redirect_stdout(io.StringIO()):
            shell.freeze(self.root, self.home)
        self.assertIn(shell.git(self.repo, "rev-parse", "HEAD"), self.snapshot.read_text())


if __name__ == "__main__":
    unittest.main()
