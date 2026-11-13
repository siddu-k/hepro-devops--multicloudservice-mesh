#!/usr/bin/env bash
# 04-bookinfo.sh -- deploy the Bookinfo sample application to BOTH clusters.
#
# Two things the original PDF gets wrong, fixed here:
#   1. the namespace must be labelled for injection BEFORE the pods exist
#   2. bookinfo-gateway.yaml is never applied in the PDF, so /productpage is
#      unreachable and every later traffic/observability step shows nothing
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

say "Labeling namespace 'default' for Envoy sidecar injection"
for ctx in "$CTX1" "$CTX2"; do
  kubectl label namespace default istio-injection=enabled --context "$ctx" --overwrite >/dev/null
  ok "$ctx"
done

say "Deploying Bookinfo to both clusters"
for ctx in "$CTX1" "$CTX2"; do
  kubectl apply -f "${ISTIO_DIR}/samples/bookinfo/platform/kube/bookinfo.yaml" --context "$ctx" >/dev/null
  kubectl apply -f "${ISTIO_DIR}/samples/bookinfo/networking/bookinfo-gateway.yaml" --context "$ctx" >/dev/null
  ok "$ctx: 4 services + versioned deployments + gateway"
done

say "Waiting for deployments"
for ctx in "$CTX1" "$CTX2"; do
  kubectl wait --for=condition=available deployment --all -n default \
    --context "$ctx" --timeout=480s >/dev/null
  ok "$ctx ready"
done

say "Pods (2/2 means app + istio-proxy)"
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl get pods -n default --context "$ctx"
done

say "Sidecar injection proof"
# Istio 1.32 injects istio-proxy as a NATIVE sidecar: an initContainer with
# restartPolicy=Always. That is why the pod shows 2/2 while spec.containers
# still lists only the application container.
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl get pods -n default --context "$ctx" \
    -o jsonpath='{range .items[*]}{.metadata.name}{" : app="}{.spec.containers[*].name}{"  | init="}{.spec.initContainers[*].name}{"\n"}{end}'
done

say "Ingress gateway addresses"
for ctx in "$CTX1" "$CTX2"; do
  ip="$(ingress_ip "$ctx")"
  [ -n "$ip" ] && ok "$ctx  http://${ip}/productpage" || warn "$ctx has no ingress VIP yet"
done

cat <<EOF

Bookinfo is running in both clusters with Envoy sidecars.

Evidence to capture now:
  kubectl get pods -n default --context ${CTX1}
  curl -s http://<ingress-ip>/productpage | head -20

Next: ./scripts/05-mtls.sh
EOF