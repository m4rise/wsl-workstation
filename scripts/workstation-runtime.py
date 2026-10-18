#!/usr/bin/env python3
"""Host probes for workstation:doctor; no project policy or account inspection."""

import argparse
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env=None):
    """Bound each probe; never dump command output that might contain local data."""
    try:
        return subprocess.run(
            args, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20, env=env
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(args, 1, "", type(error).__name__)


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ""


def enabled(capability):
    return os.environ.get(f"WORKSTATION_{capability.upper()}") == "1"


class Runtime:
    def __init__(self, bootstrap=False):
        self.bootstrap = bootstrap
        self.failures = 0

    def check(self, success, label, remedy="", required=False):
        status = "OK" if success else "FAIL" if required else "WARN"
        self.failures += status == "FAIL"
        print(f"  [{status}] {label}" + (f"; {remedy}" if not success else ""))
        return success

    def host(self):
        try:
            release = platform.freedesktop_os_release()
        except OSError:
            release = {}
        distro = f"{release.get('ID', 'unknown')} {release.get('VERSION_ID', 'unknown')}"
        self.check(
            distro == "ubuntu 26.04",
            f"Ubuntu target: {distro}",
            "supported target is Ubuntu 26.04",
        )
        self.check(
            platform.machine() == "x86_64",
            f"Architecture: {platform.machine()}",
            "install the x86-64 distribution and binaries",
        )
        kernel = platform.release()
        self.check(
            "microsoft" in kernel.lower() and "wsl2" in kernel.lower(),
            f"WSL2 kernel: {kernel}",
            "in Windows run wsl --list --verbose; update WSL and select version 2",
        )

    def node(self):
        resolved = run("mise", "which", "node").stdout.strip()
        selected = shutil.which("node")
        valid = bool(resolved and Path(resolved).is_file())
        self.check(
            valid, f"Node resolved by mise: {resolved or 'missing'}", "mise install --locked", True
        )
        if not valid:
            return
        self.check(
            bool(selected and Path(selected).resolve() == Path(resolved).resolve()),
            f"Node PATH: {selected or 'missing'}",
            "activate mise in a fresh login shell (exec zsh -l)",
        )
        result = run(resolved, "--version")
        self.check(
            result.returncode == 0 and result.stdout.startswith("v"),
            f"Node runtime: {result.stdout.strip() if result.returncode == 0 else 'cannot start'}",
            f"inspect ldd {resolved}; install missing libraries with the bootstrap (including libatomic1)",
            True,
        )

    def bubblewrap(self):
        binary = shutil.which("bwrap")
        required = enabled("codex")
        self.check(
            bool(binary),
            f"Bubblewrap PATH binary: {binary or 'missing (Codex would use its bundled fallback)'}",
            "select codex and run mise bootstrap --update --locked",
            required,
        )
        if not binary:
            return
        real = Path(binary).resolve()
        version = run(binary, "--version")
        self.check(
            version.returncode == 0,
            f"Bubblewrap executable: {real}",
            f"inspect ldd {real}; reinstall Ubuntu bubblewrap",
            required,
        )
        # No host writes or inference: an empty network namespace and read-only root.
        result = run(
            binary,
            "--die-with-parent",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--ro-bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "/usr/bin/true",
        )
        self.check(
            result.returncode == 0,
            "Bubblewrap user/PID/network namespaces and read-only mount probe",
            f"run {binary} --unshare-user --ro-bind / / /usr/bin/true in a normal WSL session; inspect AppArmor bwrap profile and kernel namespace support; keep confinement enabled",
            required,
        )

    def systemd(self):
        self.check(
            read("/proc/1/comm") == "systemd",
            "systemd is PID 1",
            "enable [boot] systemd=true in /etc/wsl.conf; save work, then wsl --shutdown from Windows and reopen Ubuntu",
        )
        manager = run("systemctl", "--user", "show", "--property=ControlGroup", "--value")
        group = manager.stdout.strip()
        self.check(
            manager.returncode == 0 and group.startswith("/") and group != "/",
            "systemd user manager reachable",
            "bootstrap wsl (dbus-user-session/libpam-systemd), then reopen a normal WSL login; check systemctl --user status and XDG_RUNTIME_DIR",
        )

    def interop(self):
        binary = shutil.which("cmd.exe")
        fallback = Path("/mnt/c/Windows/System32/cmd.exe")
        if not binary and fallback.is_file():
            binary = str(fallback)
        result = run(binary, "/d", "/c", "exit 0") if binary else None
        self.check(
            result is not None and result.returncode == 0,
            f"Windows interop: {binary or 'cmd.exe missing'}",
            "enable WSL interop and the Windows mount, then reopen WSL; do not disable the sandbox",
            enabled("wsl"),
        )

    def docker(self):
        binary = shutil.which("docker")
        # Desktop's Linux CLI is commonly symlinked under /mnt/wsl; Windows .exe is not sufficient.
        linux_cli = bool(
            binary and not binary.endswith(".exe") and not binary.startswith("/mnt/c/")
        )
        self.check(
            linux_cli,
            f"Docker WSL CLI: {binary or 'missing'}",
            "install/start Docker Desktop on Windows, select WSL2 engine and enable this distro in Settings > Resources > WSL Integration",
        )
        if self.bootstrap:
            print("  [SKIP] Docker daemon/Compose: optional in --bootstrap")
            return
        if not linux_cli:
            return
        # Probe Desktop's local socket without reading ~/.docker or using a remote context.
        with tempfile.TemporaryDirectory(prefix="workstation-docker-probe-") as directory:
            env = dict(os.environ)
            for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
                env.pop(key, None)
            env["DOCKER_CONFIG"] = directory
            args = (binary, "--host", "unix:///var/run/docker.sock")
            result = run(*args, "info", "--format", "{{.OperatingSystem}}", env=env)
            compose = run(*args, "compose", "version", env=env)
        self.check(
            result.returncode == 0 and "docker desktop" in result.stdout.lower(),
            "Docker Desktop daemon reachable through WSL integration",
            "start Docker Desktop, enable this distro's integration at /var/run/docker.sock; a separate Linux/remote engine does not validate Desktop integration",
        )
        self.check(
            compose.returncode == 0,
            "Docker Compose available",
            "repair/update Docker Desktop WSL integration",
            result.returncode == 0,
        )

    def codex(self):
        standalone = Path.home() / ".local/bin/codex"
        selected = shutil.which("codex")
        required = enabled("codex")
        exists = standalone.is_file() and os.access(standalone, os.X_OK)
        if not self.check(
            exists, f"Codex standalone: {standalone}", "mise run codex:install", required
        ):
            return
        real = standalone.resolve()
        self.check(
            bool(selected and Path(selected).resolve() == real),
            f"Codex PATH: {selected or 'missing'}; standalone target: {real}",
            "open a fresh login shell; remove PATH shadowing of the standalone",
            required,
        )
        # Version/help only, with a disposable CODEX_HOME; never read authentication/configuration.
        with tempfile.TemporaryDirectory(prefix="workstation-codex-probe-") as directory:
            env = dict(os.environ, CODEX_HOME=directory)
            result = run(str(standalone), "--version", env=env)
            self.check(
                result.returncode == 0,
                f"Codex standalone: {result.stdout.strip() if result.returncode == 0 else 'cannot start (--version)'}",
                f"inspect ldd {real}; mise run codex:update",
                required,
            )
            helper = real.with_name("codex-code-mode-host")
            result = run(str(helper), "--help", env=env)
            self.check(
                helper.is_file() and result.returncode == 0,
                f"Codex associated helper: {helper}",
                "mise run codex:update; if the upstream layout changed, adapt this probe after checking the new release; no substitute helper or historical pin",
                required,
            )
            if not enabled("wsl"):
                return
            result = run("bash", str(ROOT / "scripts/codex-agent-host.sh"), "check", env=env)
            self.check(
                result.returncode == 0,
                "VS Code Agent Host link resolves to standalone",
                "mise run codex:install",
                required,
            )

    def diagnose(self):
        print("==> General host diagnostic (optional prerequisites warn)")
        self.host()
        self.node()
        if enabled("codex"):
            self.bubblewrap()
            self.codex()
        if enabled("wsl"):
            self.systemd()
            self.interop()
        if enabled("docker"):
            self.docker()
        print(f"  Runtime failures: {self.failures}")
        return int(self.failures > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap", action="store_true", help="skip optional Docker daemon checks"
    )
    args = parser.parse_args()
    return Runtime(bootstrap=args.bootstrap).diagnose()


if __name__ == "__main__":
    raise SystemExit(main())
