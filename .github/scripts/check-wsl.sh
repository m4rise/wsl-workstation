#!/usr/bin/env bash
# Verify native interop both after bootstrap and in a new WSL boot.
set -euo pipefail

case "${1:-}" in
"" | --after-reboot | --after-terminate) ;;
*)
    echo "Usage: check-wsl.sh [--after-reboot|--after-terminate]" >&2
    exit 2
    ;;
esac

for legacy in \
    /usr/local/sbin/ensure-wsl-interop \
    /etc/systemd/system/wsl-interop-fix.service \
    /etc/systemd/system/wsl-interop-fix.timer; do
    test ! -e "$legacy"
    test ! -L "$legacy"
done
if systemctl is-enabled --quiet wsl-interop-fix.timer ||
    systemctl is-active --quiet wsl-interop-fix.timer; then
    echo "Legacy WSLInterop timer remains enabled or active" >&2
    exit 1
fi

override=/etc/systemd/system/systemd-binfmt.service.d/override.conf
test -f "$override"
grep -Fxq 'ConditionVirtualization=!wsl' "$override"
test "$(systemctl show --property=LoadState --value systemd-binfmt.service)" = loaded
if systemctl is-failed --quiet systemd-binfmt.service; then
    echo "systemd-binfmt.service failed" >&2
    exit 1
fi

interop=/proc/sys/fs/binfmt_misc/WSLInterop
test -r "$interop"
cat "$interop"
grep -qx 'enabled' "$interop"
grep -qx 'interpreter /init' "$interop"
grep -qx 'flags: PF' "$interop"
(
    cd /mnt/c
    /mnt/c/Windows/System32/cmd.exe /d /c 'exit 0'
    /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -Command 'exit 0'
)

if [[ -n "${1:-}" ]]; then
    if [[ "$1" == --after-reboot ]]; then
        test "$(cat /proc/sys/kernel/random/boot_id)" != "$(cat /var/tmp/workstation-wsl-boot-id)"
    else
        # Local isolation: terminating one distro restarts PID 1 while other
        # distros keep the shared WSL kernel and its boot_id alive.
        test "$(awk '{print $22}' /proc/1/stat)" != "$(cat /var/tmp/workstation-wsl-init-start)"
    fi
    # Bound systemd startup; a degraded state must remain a test failure.
    state="$(timeout 120 systemctl is-system-running --wait)"
    test "$state" = running
    test "$(systemctl show --property=ActiveState --value systemd-binfmt.service)" = inactive
    test "$(systemctl show --property=ConditionResult --value systemd-binfmt.service)" = no
    status=0
    report="$(systemctl status systemd-binfmt.service --no-pager)" || status=$?
    test "$status" -eq 3
    printf '%s\n' "$report"
    grep -Fq 'ConditionVirtualization=!wsl' <<<"$report"
    runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise bootstrap status --missing'
    runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run workstation:config-audit --check'
    runuser -l contributor -c 'cd ~/.config/mise && ~/.local/bin/mise run workstation:doctor --bootstrap'
fi
