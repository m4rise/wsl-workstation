"""Exercise host refusals with a fresh, fictitious user and no external services."""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime", ROOT / "scripts/workstation-runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)
RUN_PROBE = runtime.run


class ProbeInputTests(unittest.TestCase):
    def test_probe_cannot_consume_callers_script_input(self):
        program = f"""
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('runtime', {str(ROOT / "scripts/workstation-runtime.py")!r})
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
runtime.run(sys.executable, '-c', 'import sys; sys.stdin.read()')
print(sys.stdin.read(), end='')
"""
        result = subprocess.run(
            [sys.executable, "-c", program],
            input="remaining caller input\n",
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout, "remaining caller input\n")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workstation-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "user"
        self.bin = self.home / ".local/bin"
        self.bin.mkdir(parents=True)
        for name in ("node", "codex", "codex-code-mode-host", "bwrap", "docker", "cmd.exe"):
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.results = {}
        self.reads = {
            "/proc/1/comm": "systemd",
            "/sys/fs/cgroup/cgroup.controllers": "cpu io memory pids",
            "/sys/fs/cgroup/user.slice/user-1234.slice/user@1234.service/cgroup.controllers": "cpu memory pids",
        }
        self.calls = []
        self.missing = set()
        self.overrides = {}
        patches = [
            mock.patch.dict(
                os.environ, {f"WORKSTATION_{c}": "1" for c in ("CODEX", "WSL", "DOCKER")}
            ),
            mock.patch.object(runtime.Path, "home", return_value=self.home),
            mock.patch.object(runtime.os, "getuid", return_value=1234),
            mock.patch.object(
                runtime.platform,
                "freedesktop_os_release",
                return_value={"ID": "ubuntu", "VERSION_ID": "26.04"},
            ),
            mock.patch.object(runtime.platform, "machine", return_value="x86_64"),
            mock.patch.object(
                runtime.platform, "release", return_value="6.18-microsoft-standard-WSL2"
            ),
            mock.patch.object(runtime.shutil, "which", side_effect=self.which),
            mock.patch.object(
                runtime, "read", side_effect=lambda path: self.reads.get(str(path), "")
            ),
            mock.patch.object(runtime, "run", side_effect=self.run_probe),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def which(self, name):
        return None if name in self.missing else self.overrides.get(name, str(self.bin / name))

    def run_probe(self, *args, env=None):
        self.calls.append(args)
        key = Path(args[0]).name
        default = {
            "mise": str(self.bin / "node"),
            "node": "v99.0.0",
            "codex": "codex-cli 99.0.0",
            "systemctl": "/user.slice/user-1234.slice/user@1234.service",
            "docker": "Docker Desktop",
        }.get(key, "")
        code, output = self.results.get(key, (0, default))
        if key == "codex":
            self.assertNotEqual(env["CODEX_HOME"], str(self.home / ".codex"))
        return subprocess.CompletedProcess(args, code, output, "")

    def diagnose(self, agentic=True, bootstrap=False):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = runtime.Runtime(agentic, bootstrap).diagnose()
        return code, output.getvalue()

    def test_common_prerequisites_pass_without_inference_or_historical_version(self):
        code, output = self.diagnose()
        self.assertEqual(code, 0, output)
        self.assertIn("v99.0.0", output)
        self.assertTrue(any(call[0] == "systemd-run" for call in self.calls))
        self.assertFalse(any("exec" in call or "login" in call for call in self.calls))
        self.assertTrue(any("--unshare-net" in call and "--ro-bind" in call for call in self.calls))

    def test_generic_does_not_require_optional_capabilities_or_services(self):
        with mock.patch.dict(
            os.environ, {f"WORKSTATION_{c}": "0" for c in ("CODEX", "WSL", "DOCKER")}
        ):
            self.missing.update(("bwrap", "codex", "docker", "cmd.exe"))
            code, output = self.diagnose(agentic=False, bootstrap=True)
            self.assertEqual(code, 0, output)
            self.assertEqual({Path(c[0]).name for c in self.calls}, {"mise", "node"})
            code, output = self.diagnose()
            self.assertEqual(code, 1)
            self.assertIn("Capability codex selected", output)
            self.assertIn("profile:select replaces", output)

    def test_missing_or_failing_bubblewrap_is_actionable(self):
        self.missing.add("bwrap")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("mise bootstrap --update --locked", output)
        self.missing.clear()
        self.results["bwrap"] = (1, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("keep confinement enabled", output)

    def test_missing_user_manager_warns_generally_and_fails_strictly(self):
        self.results["systemctl"] = (1, "")
        code, output = self.diagnose(agentic=False, bootstrap=True)
        self.assertEqual(code, 0, output)
        self.assertIn("[WARN] systemd user manager", output)
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("dbus-user-session/libpam-systemd", output)

    def test_each_required_controller_at_root_and_user_subtree(self):
        for path in list(self.reads)[1:]:
            original = self.reads[path]
            for controller in runtime.CONTROLLERS:
                with self.subTest(path=path, controller=controller):
                    self.reads[path] = " ".join(runtime.CONTROLLERS - {controller})
                    code, output = self.diagnose()
                    self.assertEqual(code, 1, output)
            self.reads[path] = original

    def test_failed_transient_resource_unit_is_refused(self):
        self.results["systemd-run"] = (1, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("keep resource limits enabled", output)

    def test_non_wsl_wrong_os_architecture_and_root_are_refused(self):
        for patch, message in [
            (
                mock.patch.object(runtime.platform, "release", return_value="linux-microsoft"),
                "WSL2 kernel",
            ),
            (
                mock.patch.object(runtime.platform, "machine", return_value="aarch64"),
                "Architecture",
            ),
            (
                mock.patch.object(
                    runtime.platform, "freedesktop_os_release", return_value={"ID": "debian"}
                ),
                "Ubuntu target",
            ),
            (mock.patch.object(runtime.os, "getuid", return_value=0), "Non-root"),
        ]:
            with patch:
                code, output = self.diagnose()
                self.assertEqual(code, 1)
                self.assertIn(f"[FAIL] {message}", output)

    def test_interop_failure_is_refused(self):
        self.results["cmd.exe"] = (1, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("enable WSL interop", output)

    def test_docker_missing_unreachable_or_wrong_engine_is_refused(self):
        self.missing.add("docker")
        self.assertEqual(self.diagnose()[0], 1)
        self.missing.clear()
        for result in ((1, ""), (0, "Ubuntu")):
            self.results["docker"] = result
            code, output = self.diagnose()
            self.assertEqual(code, 1)
            self.assertIn("a separate Linux/remote engine", output)
        self.results["docker"] = (1, "")
        code, output = self.diagnose(agentic=False, bootstrap=True)
        self.assertEqual(code, 0, output)
        self.assertIn("[SKIP] Docker", output)

    def test_windows_docker_cli_is_not_wsl_integration(self):
        self.overrides["docker"] = "/mnt/c/Program Files/Docker/docker.exe"
        self.assertEqual(self.diagnose()[0], 1)

    def test_missing_codex_helper_and_shadowed_standalone_are_refused(self):
        helper = self.bin / "codex-code-mode-host"
        helper.unlink()
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("mise run codex:update", output)
        helper.touch()
        self.overrides["codex"] = "/usr/bin/codex"
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("PATH shadowing", output)

    def test_unloadable_node_and_path_shadowing_are_refused(self):
        self.results["node"] = (127, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("libatomic1", output)
        self.results.clear()
        self.overrides["node"] = "/usr/bin/node"
        self.assertEqual(self.diagnose()[0], 1)
        self.assertEqual(self.diagnose(agentic=False, bootstrap=True)[0], 0)

    def test_missing_mise_node_and_standalone_are_refused(self):
        self.results["mise"] = (1, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("Node resolved by mise: missing", output)
        self.results.clear()
        (self.bin / "codex").unlink()
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("mise run codex:install", output)

    def test_unloadable_helper_is_refused(self):
        self.results["codex-code-mode-host"] = (127, "")
        code, output = self.diagnose()
        self.assertEqual(code, 1)
        self.assertIn("upstream layout changed", output)

    def test_docker_probe_ignores_credentials_and_remote_context(self):
        with mock.patch.object(runtime, "run", wraps=self.run_probe) as probe:
            code, output = self.diagnose()
            self.assertEqual(code, 0, output)
        for call in probe.call_args_list:
            if Path(call.args[0]).name == "docker":
                self.assertIn("unix:///var/run/docker.sock", call.args)
                self.assertNotEqual(call.kwargs["env"]["DOCKER_CONFIG"], str(self.home / ".docker"))
                self.assertNotIn("DOCKER_CONTEXT", call.kwargs["env"])

    def test_probe_timeout_is_reported_as_failure(self):
        # Exercise the actual command wrapper without launching anything.
        with mock.patch.object(
            runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 20)
        ):
            self.assertEqual(RUN_PROBE("probe").returncode, 1)


if __name__ == "__main__":
    unittest.main()
