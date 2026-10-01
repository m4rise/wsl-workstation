import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_native_selection_generic_personal_and_subset(self):
        with tempfile.TemporaryDirectory(prefix="workstation-profile-") as directory:
            root = Path(directory)
            for file in ROOT.glob("config*.toml"):
                if ".local." not in file.name:
                    shutil.copyfile(file, root / file.name)
            env = os.environ.copy()
            for name in [
                "MISE_ENV",
                "MISE_GLOBAL_CONFIG_FILE",
                "MISE_CONFIG_FILE",
                "MISE_OVERRIDE_CONFIG_FILENAMES",
            ]:
                env.pop(name, None)
            env.update(
                MISE_CONFIG_DIR=str(root),
                MISE_GLOBAL_CONFIG_ROOT=str(root),
                MISE_SYSTEM_CONFIG_DIR=str(root / "system"),
                MISE_CACHE_DIR=str(root / "cache"),
                MISE_STATE_DIR=str(root / "state"),
                MISE_TRUSTED_CONFIG_PATHS=str(root),
            )
            capabilities = {"github", "cloud", "codex", "docker", "wsl", "secrets", "vault"}
            for selection, active in [
                ("generic", set()),
                ("personal", capabilities),
                ("wsl", {"wsl"}),
            ]:
                subprocess.run(
                    ["python3", str(ROOT / "scripts/profile.py"), selection],
                    env=env,
                    cwd=root,
                    check=True,
                    capture_output=True,
                )
                result = subprocess.run(
                    ["mise", "env", "--json"], env=env, cwd=root, check=True, capture_output=True
                )
                resolved = json.loads(result.stdout)
                for capability in capabilities:
                    self.assertEqual(
                        resolved[f"WORKSTATION_{capability.upper()}"],
                        "1" if capability in active else "0",
                    )
            (root / "miserc.toml").write_text('env = ["wsl"]\n# retained\n')
            subprocess.run(
                ["python3", str(ROOT / "scripts/profile.py"), "personal"],
                env=env,
                cwd=root,
                check=True,
                capture_output=True,
            )
            self.assertIn("# retained", (root / "miserc.toml").read_text())
            result = subprocess.run(
                ["python3", str(ROOT / "scripts/profile.py"), "unknown"],
                env=env,
                cwd=root,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
