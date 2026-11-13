#!/usr/bin/env bash
# 01-wsl-preflight.sh -- one-time host tuning. Run as root.
#
# Two things on this machine broke cluster creation until they were fixed:
#   1. WSL only had 7.5 GB -> the second node's systemd could not start
#   2. fs.inotify.max_user_instances=128 -> exhausted by the first cluster,
#      so the second node failed with "Failed to create inotify object"
# This script fixes (2) permanently and prints the (1) instructions.
set -euo pipefail

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "Kernel tuning for Kubernetes"
cat > /etc/sysctl.d/99-kubernetes-kind.conf <<'EOF'
# kind / Kubernetes need far more inotify instances than the default 128
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches   = 1048576
fs.inotify.max_queued_events  = 32768
fs.file-max                   = 2097152
net.ipv4.ip_forward           = 1
EOF
sysctl --system >/dev/null 2>&1
sysctl fs.inotify.max_user_instances fs.inotify.max_user_watches | sed 's/^/  /'

say "WSL memory"
MEM_MB="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)"
echo "  current: ${MEM_MB} MB"
if [ "$MEM_MB" -lt 7000 ]; then
  cat <<'EOF'
  Too low. On Windows, create C:\Users\<you>\.wslconfig with:

    [wsl2]
    memory=9GB
    processors=12
    swap=6GB

  then run:  wsl --shutdown
EOF
else
  echo "  OK - enough for two clusters plus Istio and the add-ons"
fi

cat <<'EOF'

IMPORTANT for anyone repeating this on Windows:
WSL shuts the distro down when the last shell exits, which kills every
container. Keep one session open while working:

    wsl -d Ubuntu -u root -- sleep infinity

EOF