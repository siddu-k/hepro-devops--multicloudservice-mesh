#!/usr/bin/env bash
# run-all.sh -- build the entire project end to end.
# Stops at the first failure so the error is obvious.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

steps=(
  02-clusters-up.sh
  03-istio-multicluster.sh
  03b-shared-ca.sh
  04-bookinfo.sh
  05-mtls.sh
  06-traffic-routing.sh
  07-addons.sh
  08-generate-traffic.sh
  09-verify.sh
  10-resilience.sh
)

start=$(date +%s)
for s in "${steps[@]}"; do
  printf '\n\033[1;35m########## %s ##########\033[0m\n' "$s"
  bash "./${s}"
done
end=$(date +%s)
printf '\n\033[1;32mAll steps completed in %d minutes.\033[0m\n' $(( (end-start)/60 ))
echo "Evidence: evidence/"
echo "Teardown: bash scripts/99-teardown.sh"