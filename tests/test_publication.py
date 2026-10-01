"""Export reviewed Git blobs and reject private content before writing a destination."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publication", ROOT / "scripts/prepare-public.py")
publication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication)
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_public", ROOT / "scripts/verify-public.py"
)
verification = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(verification)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workstation-publication-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.output = self.root / "export"
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)
        (self.repo / "README.md").write_text("Public fixture\n")
        self.commit()

    def commit(self):
        subprocess.run(["git", "-C", str(self.repo), "add", "--all"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ],
            check=True,
        )

    def invoke(self, *arguments):
        with (
            mock.patch.object(publication, "ROOT", self.repo),
            mock.patch("sys.argv", ["prepare-public", "--output", str(self.output), *arguments]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return publication.main()

    def reject(self, *arguments):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke(*arguments)
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_default_export_uses_commit_not_uncommitted_or_untracked_files(self):
        (self.repo / "README.md").write_text("unreviewed replacement\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/unreviewed.md").write_text("unreviewed new file\n")
        self.assertEqual(self.invoke(), 0)
        self.assertEqual((self.output / "README.md").read_text(), "Public fixture\n")
        self.assertFalse((self.output / "docs/unreviewed.md").exists())
        manifest = self.output.with_name("export.manifest.json")
        self.assertEqual(verification.verify(self.output, manifest), 1)
        self.assertFalse(json.loads(manifest.read_text())["working_tree"])

    def test_working_tree_preview_is_explicit_and_preserves_executable_mode(self):
        (self.repo / "tasks").mkdir()
        file = self.repo / "tasks/example"
        file.write_text("#!/usr/bin/env bash\nexit 0\n")
        file.chmod(0o755)
        self.assertEqual(self.invoke("--working-tree"), 0)
        manifest = self.output.with_name("export.manifest.json")
        self.assertEqual(verification.verify(self.output, manifest), 2)
        self.assertTrue(json.loads(manifest.read_text())["working_tree"])
        file = self.output / "tasks/example"
        file.chmod(0o644)
        with self.assertRaises(ValueError):
            verification.verify(self.output, manifest)

    def test_private_names_are_rejected_in_a_committed_reference(self):
        directory = self.repo / "docs"
        directory.mkdir()
        file = directory / "identity.conf"
        file.write_text("private fixture\n")
        self.commit()
        self.reject()

    def test_symlinks_are_rejected_in_git_tree_and_working_tree(self):
        directory = self.repo / "docs"
        directory.mkdir()
        (directory / "guide.md").symlink_to(self.repo / "README.md")
        self.commit()
        self.reject()
        self.reject("--working-tree")

    def test_personal_paths_and_private_markers_are_rejected_without_printing_values(self):
        file = self.repo / "README.md"
        file.write_text("Personal path: /home/" + "fixture-owner\n")
        self.commit()
        self.reject()
        file.write_text("private-mail-marker\n")
        self.commit()
        markers = self.root / "markers.txt"
        markers.write_text("private-mail-marker\n")
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
            self.invoke("--markers-file", str(markers))
        self.assertNotIn("private-mail-marker", output.getvalue())

    def test_manifest_detects_changed_and_added_files(self):
        self.invoke()
        manifest = self.output.with_name("export.manifest.json")
        (self.output / "extra.txt").write_text("unreviewed\n")
        with self.assertRaises(ValueError):
            verification.verify(self.output, manifest)
        (self.output / "extra.txt").unlink()
        (self.output / "README.md").write_text("changed\n")
        with self.assertRaises(ValueError):
            verification.verify(self.output, manifest)

    def test_export_still_has_no_history_after_source_has_multiple_commits(self):
        (self.repo / "README.md").write_text("second public fixture\n")
        self.commit()
        self.invoke()
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", str(self.output), "rev-list", "--all", "--count"]
            ).strip(),
            b"0",
        )
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(self.output), "remote"]).strip(), b""
        )

    def test_symlink_ancestor_of_output_is_rejected(self):
        link = self.root / "linked-output"
        link.symlink_to(self.root, target_is_directory=True)
        self.output = link / "export"
        self.reject()


if __name__ == "__main__":
    unittest.main()
