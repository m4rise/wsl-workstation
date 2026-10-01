#!/usr/bin/env python3
"""Load and validate the shared mise installer metadata without executing it."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_metadata(root=ROOT):
    data = json.loads((root / "system/bootstrap/mise.json").read_text())
    if set(data) != {"version", "installer_sha256"}:
        raise ValueError("Unexpected bootstrap metadata fields")
    if not isinstance(data["version"], str) or not re.fullmatch(
        r"\d{4}\.\d+\.\d+", data["version"]
    ):
        raise ValueError("Invalid mise version")
    if not isinstance(data["installer_sha256"], str) or not re.fullmatch(
        r"[a-f0-9]{64}", data["installer_sha256"]
    ):
        raise ValueError("Invalid installer checksum")
    config = tomllib.loads((root / "config.toml").read_text())
    minimum = config["min_version"]
    if not isinstance(minimum, str) or not re.fullmatch(r"\d{4}\.\d+\.\d+", minimum):
        raise ValueError("Invalid minimum mise version")
    if version_tuple(data["version"]) < version_tuple(minimum):
        raise ValueError("Installer version is below the configuration minimum")
    return data


def version_tuple(value):
    return tuple(int(part) for part in value.split("."))


if __name__ == "__main__":
    metadata = load_metadata()
    print(f"version={metadata['version']}")
