#!/usr/bin/env bash
# lib.sh -- shared helpers for the DevOps Project 5 scripts.
# Source this file; do not execute it.
# shellcheck shell=bash

CTX1="${CTX1:-kind-mesh1}"
CTX2="${CTX2:-kind-mesh2}"
NAME1="${NAME1:-mesh1}"
NAME2="${NAME2:-mesh2}"
UNDERLAY="${UNDERLAY:-mesh-underlay}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m WARN\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

resolve_istio() {
  if [ -n "${ISTIO_DIR:-}" ] && [ -x "${ISTIO_DIR}/bin/istioctl" ]; then return 0; fi
  local d best=""
  for d in /root/istio-* "$HOME"/istio-* /home/*/istio-*; do
    [ -x "$d/bin/istioctl" ] && best="$d"
  done
  [ -n "$best" ] || die "istioctl not found - run scripts/00-install-tools.sh"
  ISTIO_DIR="$best"
}

init() {
  resolve_istio
  export PATH="${ISTIO_DIR}/bin:${PATH}"
  command -v kubectl >/dev/null 2>&1 || die "kubectl not found"
  local have
  have="$(kubectl config get-contexts -o name)"
  echo "$have" | grep -qx "$CTX1" || die "kubectl context ${CTX1} missing - run scripts/02-clusters-up.sh"
  echo "$have" | grep -qx "$CTX2" || die "kubectl context ${CTX2} missing - run scripts/02-clusters-up.sh"
  ok "istio ${ISTIO_DIR} , contexts ${CTX1} + ${CTX2}"
}

underlay_ip() {
  docker network inspect "$UNDERLAY" -f '{{range .Containers}}{{.Name}}={{.IPv4Address}} {{end}}' \
    | tr ' ' '\n' | awk -F'[=/]' -v n="$1" '$1==n {print $2}'
}

ingress_ip() {
  kubectl -n istio-system get svc istio-ingressgateway --context "$1" \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true
}

eastwest_ip() {
  kubectl -n istio-system get svc istio-eastwestgateway --context "$1" \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true
}

# Creates (or reuses) an in-mesh curl pod used to generate east-west traffic.
#
# It MUST be recreated if it is older than the `cacerts` secret: the pod's
# istio-proxy holds a certificate issued by whatever CA was active when it
# started. After 03b-shared-ca.sh replaces that CA, a stale client keeps
# presenting an untrusted certificate and every request returns 503 - which
# looks exactly like a routing failure but is a certificate failure.
ensure_traffic_client() {
  local ctx="$1"
  local pod_ts secret_ts
  if kubectl -n default get pod traffic-client --context "$ctx" >/dev/null 2>&1; then
    pod_ts="$(kubectl -n default get pod traffic-client --context "$ctx" \
      -o jsonpath='{.metadata.creationTimestamp}' 2>/dev/null || true)"
    secret_ts="$(kubectl -n istio-system get secret cacerts --context "$ctx" \
      -o jsonpath='{.metadata.creationTimestamp}' 2>/dev/null || true)"
    if [ -n "$secret_ts" ] && [[ "$pod_ts" < "$secret_ts" ]]; then
      warn "traffic-client predates the shared CA - recreating it"
      kubectl -n default delete pod traffic-client --context "$ctx" >/dev/null 2>&1 || true
    else
      kubectl -n default wait --for=condition=Ready pod/traffic-client \
        --context "$ctx" --timeout=180s >/dev/null
      return 0
    fi
  fi
  cat <<'EOF' | kubectl apply -f - --context "$ctx" >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: traffic-client
  namespace: default
  labels:
    app: traffic-client
spec:
  containers:
  - name: curl
    image: curlimages/curl:8.10.1
    command: ["sleep", "3600"]
EOF
  kubectl -n default wait --for=condition=Ready pod/traffic-client --context "$ctx" --timeout=240s >/dev/null
}