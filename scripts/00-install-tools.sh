#!/usr/bin/env bash
# 00-install-tools.sh -- install the CLIs needed for DevOps Project 5.
# Safe to re-run. Run inside WSL Ubuntu.
set -euo pipefail

ISTIO_VERSION="${ISTIO_VERSION:-1.24.3}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }

say "Checking base packages"
need_apt=()
command -v jq      >/dev/null 2>&1 || need_apt+=(jq)
command -v unzip   >/dev/null 2>&1 || need_apt+=(unzip)
command -v curl    >/dev/null 2>&1 || need_apt+=(curl)
if [ ${#need_apt[@]} -gt 0 ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq "${need_apt[@]}"
fi
ok "jq $(jq --version)"
ok "unzip $(unzip -v | head -1 | awk '{print $2}')"

say "Docker"
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not reachable. Start it with: sudo service docker start" >&2
  exit 1
fi
ok "docker $(docker version --format '{{.Server.Version}}')"

say "kind"
if command -v kind >/dev/null 2>&1; then
  ok "$(kind version)"
else
  curl -sSLo /tmp/kind https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64
  chmod +x /tmp/kind && sudo mv /tmp/kind /usr/local/bin/kind
  ok "$(kind version)"
fi

say "kubectl"
command -v kubectl >/dev/null 2>&1 && ok "$(kubectl version --client 2>/dev/null | head -1)" || echo "kubectl missing" >&2

say "istioctl ${ISTIO_VERSION}"
WORK="${HOME}/istio-dl"
mkdir -p "$WORK"
if [ ! -x "${HOME}/istio-${ISTIO_VERSION}/bin/istioctl" ]; then
  curl -sSL "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istio-${ISTIO_VERSION}-linux-amd64.tar.gz" -o "$WORK/istio.tgz"
  tar -xzf "$WORK/istio.tgz" -C "$HOME"
fi
export PATH="${HOME}/istio-${ISTIO_VERSION}/bin:${PATH}"
ok "$(istioctl version --remote=false 2>/dev/null | head -1)"

say "Optional cloud CLIs (needed only for the EKS phase)"
if command -v aws >/dev/null 2>&1; then ok "aws $(aws --version 2>&1 | cut -d' ' -f1)"; else echo "  aws CLI not installed (fine for the local phase)"; fi
if command -v eksctl >/dev/null 2>&1; then ok "$(eksctl version)"; else echo "  eksctl not installed (fine for the local phase)"; fi

cat <<EOF

Next: source the environment, then create the clusters.

  export PATH="\$HOME/istio-${ISTIO_VERSION}/bin:\$PATH"
  ./scripts/02-clusters-up.sh
EOF