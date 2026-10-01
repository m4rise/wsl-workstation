#!/usr/bin/env python3
"""Install verified mise on a fresh account; preserve a supported existing binary."""

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from bootstrap_metadata import ROOT, load_metadata, version_tuple


def main():
    if len(sys.argv) != 1:
        print("Usage: python3 scripts/install-mise.py", file=sys.stderr)
        return 2
    try:
        data = load_metadata()
        minimum = tomllib.loads((ROOT / "config.toml").read_text())["min_version"]
        binary = Path.home() / ".local/bin/mise"
        if binary.is_file() and os.access(binary, os.X_OK):
            result = subprocess.run(
                [str(binary), "--version"], capture_output=True, text=True, check=True
            )
            match = re.match(r"(\d{4}\.\d+\.\d+)", result.stdout)
            if match and version_tuple(match[1]) >= version_tuple(minimum):
                print(f"Existing mise {match[1]} satisfies the minimum; kept in place.")
                return 0
        url = f"https://github.com/jdx/mise/releases/download/v{data['version']}/install.sh"
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != data["installer_sha256"]:
            raise ValueError("Installer checksum mismatch; nothing executed")
        with tempfile.TemporaryDirectory(prefix="workstation-mise-install-") as directory:
            installer = Path(directory) / "install.sh"
            installer.write_bytes(content)
            installer.chmod(0o600)
            env = os.environ.copy()
            env.update(MISE_VERSION=data["version"], MISE_INSTALL_PATH=str(binary))
            subprocess.run(["sh", str(installer)], env=env, check=True)
        print("mise installed. Add ~/.local/bin to PATH, then run mise trust.")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, urllib.error.URLError):
        print(
            "mise installation failed; check metadata, network and filesystem access. No unchecked installer was executed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
