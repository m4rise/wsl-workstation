"""Exercise WSL migration with native mise files and an isolated system manager."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (
    "/usr/local/sbin/ensure-wsl-interop",
    "/etc/systemd/system/wsl-interop-fix.service",
    "/etc/systemd/system/wsl-interop-fix.timer",
)
OVERRIDE = "/etc/systemd/system/systemd-binfmt.service.d/override.conf"
INTEROP = "/proc/sys/fs/binfmt_misc/WSLInterop"

# Only these lifecycle operations are accepted, and every mutation is recorded.
# File changes still come from the real mise bootstrap primitive.
SYSTEMCTL = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["WSL_FIXTURE"])
state_file = root / "manager.json"
state = json.loads(state_file.read_text())
args = sys.argv[1:]
command = args[0]
unit = args[-1]
timer = "wsl-interop-fix.timer"
service = "wsl-interop-fix.service"
binfmt = "systemd-binfmt.service"
paths = json.loads(os.environ["WSL_PATHS"])
snapshot = {name: Path(name).read_text() if Path(name).exists() else None for name in paths}

if command == "is-enabled":
    sys.exit(0 if unit == timer and state["enabled"] else 1)
if command == "is-active":
    sys.exit(0 if unit == timer and state["active"] else 3)
if command == "is-failed":
    sys.exit(0 if unit == binfmt and state["failed"] else 1)
if command == "show":
    if state.get("unavailable"):
        sys.exit(1)
    if unit not in (binfmt, timer, service):
        sys.exit(2)
    if unit != binfmt and not state["legacy_loaded"]:
        sys.exit(1)
    prop = args[1]
    if prop == "--property=NeedDaemonReload":
        print("yes" if snapshot != state["snapshot"] else "no")
    elif prop == "--property=LoadState":
        print("loaded")
    elif prop == "--property=ActiveState" and unit == service:
        print("activating" if state["oneshot"] else "inactive")
    else:
        sys.exit(2)
    sys.exit(0)

if command == "disable" and args == ["disable", "--now", timer]:
    # This must precede the native removal step.
    assert all(Path(name).exists() for name in paths[:3])
    state["enabled"] = state["active"] = False
elif command == "stop" and args == ["stop", service]:
    state["oneshot"] = False
elif command == "daemon-reload" and args == ["daemon-reload"]:
    assert all(not Path(name).exists() for name in paths[:3])
    assert Path(paths[3]).read_text() == "[Unit]\nConditionVirtualization=!wsl\n"
    state["snapshot"] = snapshot
    state["legacy_loaded"] = False
elif command == "reset-failed" and args == ["reset-failed", binfmt]:
    assert snapshot == state["snapshot"]
    state["failed"] = False
else:
    sys.exit(2)
state["mutations"].append(args)
state_file.write_text(json.dumps(state))
"""


class WslTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workstation-wsl-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = {
            path: str(self.root / path.lstrip("/"))
            for path in (*LEGACY, OVERRIDE, INTEROP, str(Path(OVERRIDE).parent))
        }
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.write_executable(self.bin / "systemctl", SYSTEMCTL)
        self.write_executable(self.bin / "sudo", '#!/bin/sh\nexec "$@"\n')
        self.env = {
            k: v for k, v in os.environ.items() if not k.startswith(("MISE_", "WORKSTATION_"))
        }
        self.env.update(
            PATH=os.pathsep.join(
                [str(self.bin)]
                + [
                    path
                    for path in os.environ["PATH"].split(os.pathsep)
                    if not path.startswith("/mnt/")
                ]
            ),
            WSL_FIXTURE=str(self.root),
            WSL_PATHS=json.dumps([self.paths[path] for path in (*LEGACY, OVERRIDE)]),
            MISE_ENV="wsl",
            MISE_CONFIG_DIR=str(self.root),
            MISE_GLOBAL_CONFIG_ROOT=str(self.root),
            MISE_SYSTEM_CONFIG_DIR=str(self.root / "system-config"),
            MISE_CACHE_DIR=str(self.root / "cache"),
            MISE_STATE_DIR=str(self.root / "state"),
            MISE_DATA_DIR=str(self.root / "data"),
            MISE_TRUSTED_CONFIG_PATHS=str(self.root),
            MISE_TASK_RUN_AUTO_INSTALL="false",
            PYTHONDONTWRITEBYTECODE="1",
        )
        source_dir = self.root / "system/wsl"
        source_dir.mkdir(parents=True)
        shutil.copyfile(
            ROOT / "system/wsl/systemd-binfmt.override.conf",
            source_dir / "systemd-binfmt.override.conf",
        )
        self.migration = source_dir / "migrate-legacy-interop"
        self.migration.write_text(
            self.redirect((ROOT / "system/wsl/migrate-legacy-interop").read_text())
        )
        config = self.redirect((ROOT / "config.wsl.toml").read_text())
        config = config.replace('owner = "root"\n', "").replace('group = "root"\n', "")
        (self.root / "config.wsl.toml").write_text(config)
        (self.root / "config.toml").write_text(
            '[task_config]\nincludes = ["tasks"]\n[env]\nWORKSTATION_WSL = "0"\n'
        )
        tasks = self.root / "tasks"
        tasks.mkdir()
        # Run the real WSL finalization prefix, excluding unrelated Codex/lint/Git setup.
        prefix = (ROOT / "tasks/bootstrap").read_text().split('if [[ "${WORKSTATION_CODEX')[0]
        self.write_executable(tasks / "bootstrap", prefix)
        self.initialize_manager()

    def redirect(self, text):
        return re.sub(
            "|".join(re.escape(source) for source in self.paths),
            lambda match: self.paths[match[0]],
            text,
        )

    def write_executable(self, path, content):
        path.write_text(content)
        path.chmod(0o755)

    def initialize_manager(self, legacy=False, failed=False):
        if legacy:
            for path in LEGACY:
                file = Path(self.paths[path])
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("inert legacy fixture\n")
        self.save_manager(
            dict(
                enabled=legacy,
                active=legacy,
                oneshot=legacy,
                legacy_loaded=legacy,
                failed=failed,
                mutations=[],
                snapshot={
                    self.paths[path]: Path(self.paths[path]).read_text()
                    if Path(self.paths[path]).exists()
                    else None
                    for path in (*LEGACY, OVERRIDE)
                },
            )
        )

    def manager(self):
        return json.loads((self.root / "manager.json").read_text())

    def save_manager(self, state):
        (self.root / "manager.json").write_text(json.dumps(state))

    def run_mise(self, *args):
        result = subprocess.run(
            ["mise", *args], cwd=self.root, env=self.env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def bootstrap(self):
        self.run_mise("bootstrap", "--only", "packages,files,task", "--locked", "--yes")

    def test_wsl_declares_native_policy_and_only_absent_legacy_files(self):
        config = tomllib.loads((ROOT / "config.wsl.toml").read_text())
        self.assertEqual(config["env"]["WORKSTATION_WSL"], "1")
        for path in LEGACY:
            self.assertEqual(config["bootstrap"]["files"][path], {"state": "absent"})
        self.assertEqual(
            config["bootstrap"]["files"][OVERRIDE]["source"],
            "system/wsl/systemd-binfmt.override.conf",
        )
        self.assertNotIn("services", config["bootstrap"])
        self.assertFalse((ROOT / "system/wsl-interop").exists())

    def test_fresh_and_legacy_bootstrap_converge_without_repeated_mutations(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                Path(self.paths[OVERRIDE]).unlink(missing_ok=True)
                self.initialize_manager(legacy=legacy, failed=legacy)
                self.bootstrap()
                state = self.manager()
                expected = []
                if legacy:
                    expected += [
                        ["disable", "--now", "wsl-interop-fix.timer"],
                        ["stop", "wsl-interop-fix.service"],
                    ]
                expected += [["daemon-reload"]]
                if legacy:
                    expected += [["reset-failed", "systemd-binfmt.service"]]
                self.assertEqual(state["mutations"], expected)
                self.assertFalse(state["failed"])
                for path in LEGACY:
                    self.assertFalse(Path(self.paths[path]).exists())
                self.bootstrap()
                self.assertEqual(self.manager(), state)
                result = self.run_mise("bootstrap", "status", "--missing", "--json")
                self.assertTrue(
                    all(item["action"] == "noop" for item in json.loads(result.stdout)["files"])
                )

    def test_unselected_capability_does_not_mutate_systemd(self):
        result = subprocess.run(
            ["bash", str(self.migration)],
            cwd=self.root,
            env={**self.env, "WORKSTATION_WSL": "0"},
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.manager()["mutations"], [])

    def test_temporary_wsl_selection_propagates_to_migration_hook(self):
        self.env.pop("MISE_ENV")
        self.initialize_manager(legacy=True)
        self.run_mise(
            "-E", "wsl", "bootstrap", "--only", "packages,files,task", "--locked", "--yes"
        )
        self.assertFalse(self.manager()["enabled"])
        self.assertFalse(self.manager()["active"])

    def test_global_config_hook_uses_declaring_directory(self):
        user_root = self.root / "user-root"
        user_root.mkdir()
        self.env["MISE_GLOBAL_CONFIG_ROOT"] = str(user_root)
        self.initialize_manager(legacy=True)
        self.bootstrap()
        self.assertFalse(self.manager()["enabled"])
        self.assertFalse(self.manager()["active"])

    def doctor(self):
        script = (ROOT / "tasks/workstation/doctor").read_text()
        start = script.index('if [[ "${WORKSTATION_WSL:-0}" == 1 ]]')
        end = script.index('if [[ "${WORKSTATION_DOCKER:-0}"', start)
        block = self.redirect(script[start:end]).replace("/mnt/c", str(self.root / "windows"))
        prefix = 'set -uo pipefail\nsection() { :; }\nok() { echo "OK $*"; }\nfail() { echo "FAIL $*"; failures=$((failures + 1)); }\nfailures=0\n'
        return subprocess.run(
            ["bash", "-c", prefix + block + '\nexit "$failures"'],
            cwd=self.root,
            env={**self.env, "WORKSTATION_WSL": "1"},
            capture_output=True,
            text=True,
        )

    def test_doctor_validates_native_interop_and_rejects_drift_without_timer(self):
        self.bootstrap()
        interop = Path(self.paths[INTEROP])
        interop.parent.mkdir(parents=True)
        healthy = "enabled\ninterpreter /init\nflags: PF\n"
        interop.write_text(healthy)
        windows = self.root / "windows/Windows/System32"
        windows.mkdir(parents=True)
        self.write_executable(
            windows / "cmd.exe",
            '#!/bin/sh\ntest "$PWD" = "$WSL_FIXTURE/windows" && test "$*" = "/d /c exit 0"\n',
        )
        result = self.doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for content in (
            "",
            healthy.replace("enabled", "disabled"),
            healthy.replace("/init", "/other"),
            healthy.replace("PF", "P"),
        ):
            with self.subTest(content=content):
                interop.write_text(content)
                self.assertIn("FAIL WSLInterop handler missing or invalid", self.doctor().stdout)
        interop.unlink()
        self.assertNotEqual(self.doctor().returncode, 0)
        interop.write_text(healthy)
        for path in LEGACY:
            file = Path(self.paths[path])
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("legacy\n")
            self.assertIn("FAIL Legacy WSLInterop artifact remains", self.doctor().stdout)
            file.unlink()
        override = Path(self.paths[OVERRIDE])
        override.write_text("[Unit]\nConditionVirtualization=wsl\n")
        self.assertIn("FAIL systemd-binfmt WSL condition missing or invalid", self.doctor().stdout)
        override.unlink()
        self.assertNotEqual(self.doctor().returncode, 0)
        override.write_text("[Unit]\nConditionVirtualization=!wsl\n")
        state = self.manager()
        state["failed"] = True
        self.save_manager(state)
        self.assertIn("FAIL systemd-binfmt.service failed", self.doctor().stdout)
        state.update(failed=False, unavailable=True)
        self.save_manager(state)
        self.assertIn("FAIL Cannot inspect systemd-binfmt.service", self.doctor().stdout)
        state["unavailable"] = False
        self.save_manager(state)
        self.write_executable(windows / "cmd.exe", "#!/bin/sh\nexit 1\n")
        self.assertIn("FAIL Cannot execute Windows binaries from WSL", self.doctor().stdout)


if __name__ == "__main__":
    unittest.main()
