#!/usr/bin/env bash
# 99-teardown.sh -- delete everything and give the RAM back.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

printf '\n\033[1;33mThis deletes both clusters. Ctrl-C within 5s to abort.\033[0m\n'
sleep 5

say "Deleting clusters"
kind delete cluster --name "$NAME1" || true
kind delete cluster --name "$NAME2" || true

say "Removing the underlay network"
docker network rm "$UNDERLAY" >/dev/null 2>&1 || true

say "Remaining kind clusters"
kind get clusters 2>/dev/null || echo "(none)"

echo
echo "Done. To also free the 9 GB WSL VM, run from Windows:  wsl --shutdown"
echo "The project folder, scripts and evidence/ output stay on disk."