"""Exercise the Codex update task without downloads or a real installation."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexUpdateTests(unittest.TestCase):
    def test_sparse_path_does_not_modify_shell_profile_on_install_or_update(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            tools = home / "tools"
            tools.mkdir()
            # A competing CLI must not take precedence over the standalone.
            (tools / "codex").write_text("#!/bin/sh\nexit 99\n")
            (tools / "codex").chmod(0o755)
            installer = home / "installer.sh"
            installer.write_text(
                """#!/bin/sh
set -eu
test "$CODEX_NON_INTERACTIVE" = 1
test "$CODEX_INSTALL_DIR" = "$HOME/.local/bin"
# Reproduce upstream's PATH-based decision to append a shell block.
case ":$PATH:" in
    *":$CODEX_INSTALL_DIR:"*) ;;
    *) printf '\\n# >>> Codex installer >>>\\n' >> "$HOME/.zshrc" ;;
esac
mkdir -p "$CODEX_INSTALL_DIR"
printf '#!/bin/sh\\necho codex-cli fixture\\n' > "$CODEX_INSTALL_DIR/codex"
chmod +x "$CODEX_INSTALL_DIR/codex"
test "$(command -v codex)" = "$CODEX_INSTALL_DIR/codex"
"""
            )
            curl = tools / "curl"
            curl.write_text('#!/bin/sh\ncp "$HOME/installer.sh" "$4"\n')
            curl.chmod(0o755)
            profile = home / "profile"
            original = b"# user configuration\nexport EDITOR=vim\n"
            profile.write_bytes(original)
            (home / ".zshrc").symlink_to(profile)
            env = dict(
                os.environ,
                HOME=str(home),
                PATH=f"{tools}:/usr/bin:/bin",
                SHELL="/bin/zsh",
                WORKSTATION_CODEX="1",
                WORKSTATION_WSL="0",
                CODEX_INSTALL_DIR=str(home / "unexpected"),
            )
            for _ in range(2):
                result = subprocess.run(
                    ["bash", str(ROOT / "tasks/codex/update")],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("codex-cli fixture", result.stdout)
                self.assertTrue((home / ".zshrc").is_symlink())
                self.assertEqual(profile.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
