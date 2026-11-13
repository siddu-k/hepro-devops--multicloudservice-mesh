#!/usr/bin/env bash
# 02-clusters-up.sh -- create two INDEPENDENT Kubernetes clusters.
#
# Topology
#   mesh1  pod CIDR 10.244.0.0/16   MetalLB 172.30.0.200-209   (primary)
#   mesh2  pod CIDR 10.245.0.0/16   MetalLB 172.30.0.210-219   (remote)
#   both node containers sit on one docker bridge: mesh-underlay 172.30.0.0/24
#
# Why this shape
#   * two clusters, two API servers, two kubectl contexts  -> like EKS + GKE
#   * two pod CIDRs with NO route between them             -> multi-network
#   * MetalLB VIPs on the shared bridge                    -> like an AWS NLB
#   Istio will still refuse to let the pods talk to each other, which is the
#   whole point: the east-west gateways have to do the work.
#
# Idempotent. Safe to re-run.
set -euo pipefail

CTX1="kind-mesh1";  CTX2="kind-mesh2"
C1="mesh1";         C2="mesh2"
UNDERLAY="mesh-underlay"
UNDERLAY_SUBNET="172.30.0.0/24"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m WARN\033[0m %s\n' "$*"; }

# ------------------------------------------------------------------- preflight
say "Preflight"
docker info >/dev/null 2>&1 || { echo "docker daemon not running" >&2; exit 1; }
ok "docker $(docker version --format '{{.Server.Version}}')"

MEM_MB="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)"
if [ "$MEM_MB" -lt 7000 ]; then
  warn "only ${MEM_MB} MB RAM in WSL. Two clusters + Istio need ~7 GB."
  warn "Raise it in C:\\Users\\<you>\\.wslconfig  ->  [wsl2] memory=9GB, then: wsl --shutdown"
fi
ok "memory ${MEM_MB} MB"

# --------------------------------------------------------------- underlay net
say "Underlay network ${UNDERLAY} (${UNDERLAY_SUBNET})"
if ! docker network inspect "$UNDERLAY" >/dev/null 2>&1; then
  docker network create --subnet "$UNDERLAY_SUBNET" "$UNDERLAY" >/dev/null
  ok "created"
else
  ok "already exists"
fi

# ---------------------------------------------------------------- kind clusters
create_cluster() {
  local name="$1" cfg="$2" attempt
  if kind get clusters 2>/dev/null | grep -qx "$name"; then
    ok "cluster ${name} already exists"
    return 0
  fi
  say "Creating kind cluster ${name}"
  for attempt in 1 2 3; do
    if KIND_EXPERIMENTAL_DOCKER_NETWORK="$UNDERLAY" \
       kind create cluster --name "$name" --wait 300s --config "$cfg"; then
      return 0
    fi
    warn "attempt ${attempt} failed; cleaning up"
    kind delete cluster --name "$name" >/dev/null 2>&1 || true
    sleep 10
  done
  echo "FAILED: could not create ${name} after 3 attempts" >&2
  return 1
}

create_cluster "$C1" "${ROOT}/clusters/${C1}.yaml"
create_cluster "$C2" "${ROOT}/clusters/${C2}.yaml"

for n in "${C1}-control-plane" "${C2}-control-plane"; do
  if ! docker network inspect "$UNDERLAY" -f '{{range .Containers}}{{.Name}} {{end}}' | grep -q "$n"; then
    warn "$n was not on ${UNDERLAY}; connecting it now"
    docker network connect "$UNDERLAY" "$n"
  fi
done

underlay_ip() {
  docker network inspect "$UNDERLAY" -f '{{range .Containers}}{{.Name}}={{.IPv4Address}} {{end}}' \
    | tr ' ' '\n' | awk -F'[=/]' -v n="$1" '$1==n {print $2}'
}
NODE1_IP="$(underlay_ip "${C1}-control-plane")"
NODE2_IP="$(underlay_ip "${C2}-control-plane")"
[ -n "$NODE1_IP" ] || { echo "cannot determine ${C1} underlay IP" >&2; exit 1; }
[ -n "$NODE2_IP" ] || { echo "cannot determine ${C2} underlay IP" >&2; exit 1; }
ok "${C1}-control-plane = ${NODE1_IP}"
ok "${C2}-control-plane = ${NODE2_IP}"

# --------------------------------------------------------------------- MetalLB
install_metallb() {
  local name="$1" ctx="$2" start="$3" end="$4"
  say "MetalLB on ${ctx} (${start}-${end})"
  kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml \
    --context "$ctx" >/dev/null
  kubectl -n metallb-system wait --for=condition=Available deployment/controller \
    --timeout=240s --context "$ctx" >/dev/null
  kubectl -n metallb-system wait --for=condition=Ready pod -l component=speaker \
    --timeout=240s --context "$ctx" >/dev/null

  # advertise only on the underlay NIC, so the other cluster can answer the ARP
  local iface
  iface="$(docker exec "${name}-control-plane" sh -c \
    "ip -o -4 addr show | awk '\$4 ~ /^172\\\\.30\\\\.0/ {print \$2; exit}'" 2>/dev/null | tr -d '\r' || true)"
  iface="${iface:-eth0}"

  kubectl apply --context "$ctx" -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: underlay-pool
  namespace: metallb-system
spec:
  addresses:
  - ${start}-${end}
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: underlay-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - underlay-pool
  interfaces:
  - ${iface}
EOF
  ok "pool ${start}-${end} on ${iface}"
}

install_metallb "$C1" "$CTX1" "172.30.0.200" "172.30.0.209"
install_metallb "$C2" "$CTX2" "172.30.0.210" "172.30.0.219"

# ---------------------------------------------------------------------- sanity
say "Cluster inventory"
kubectl get nodes -o wide --context "$CTX1"
kubectl get nodes -o wide --context "$CTX2"

cat <<EOF

Two clusters are ready:

  ${CTX1}   node ${NODE1_IP}   pod CIDR 10.244.0.0/16   VIPs 172.30.0.200-209
  ${CTX2}   node ${NODE2_IP}   pod CIDR 10.245.0.0/16   VIPs 172.30.0.210-219

Next: ./scripts/03-istio-multicluster.sh
EOF