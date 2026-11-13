#!/usr/bin/env bash
# 09-verify.sh -- prove the mesh works, and capture the evidence in one file.
#
# The important check is the ENDPOINTS list: after the remote secret is in
# place, each cluster's review Service must contain pod IPs from BOTH pod CIDRs.
# 10.244.x = mesh1 pods, 10.245.x = mesh2 pods.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="${ROOT}/evidence"
mkdir -p "$OUTDIR"
OUT="${OUTDIR}/verify-${STAMP}.txt"
exec > >(tee -a "$OUT") 2>&1

echo "DevOps Project 5 - verification ${STAMP}"
echo "contexts: ${CTX1} ${CTX2}"
echo

say "1. Nodes"
kubectl get nodes -o wide --context "$CTX1"
kubectl get nodes -o wide --context "$CTX2"

say "2. All pods"
kubectl get pods -A --context "$CTX1"
kubectl get pods -A --context "$CTX2"

say "3. Istio control plane / gateways"
kubectl get pods -n istio-system --context "$CTX1"
kubectl get pods -n istio-system --context "$CTX2"

say "4. Security policy"
kubectl get peerauthentication -n default --context "$CTX1"
kubectl get peerauthentication -n default --context "$CTX2"

say "5. Traffic management"
kubectl get virtualservice,destinationrule -n default --context "$CTX1"
kubectl describe virtualservice reviews -n default --context "$CTX1" | sed -n '1,45p'

say "6. Proxy sync"
istioctl proxy-status --context "$CTX1"
istioctl proxy-status --context "$CTX2"

say "7. Remote cluster registration"
istioctl remote-clusters --context "$CTX1"
istioctl remote-clusters --context "$CTX2"

say "8. Sidecar injection (istio-proxy is a NATIVE sidecar: initContainer with restartPolicy=Always)"
kubectl get pods -n default --context "$CTX1" \
  -o jsonpath='{range .items[*]}{.metadata.name}{" : app="}{.spec.containers[*].name}{"  | init="}{.spec.initContainers[*].name}{"\n"}{end}'

say "9. CROSS-CLUSTER SERVICE DISCOVERY - the part that matters"
echo "mesh1 pod CIDR 10.244.x.x / mesh2 pod CIDR 10.245.x.x"
echo
echo "NOTE: 'kubectl get endpoints' only ever lists LOCAL pods. In a multi-network"
echo "mesh the remote cluster's pods are reachable through its east-west gateway,"
echo "so they appear in Envoy's endpoint list as <eastwest-VIP>:15443, not as pod"
echo "IPs. The authoritative check is istioctl proxy-config endpoint."
echo
POD1="$(kubectl -n default get pods -l app=productpage -o jsonpath='{.items[0].metadata.name}' --context "$CTX1")"
echo "probe pod: ${POD1} (${CTX1})"

echo
echo "--- Kubernetes view (local pods only, expected) ---"
for ctx in "$CTX1" "$CTX2"; do
  echo "  ${ctx}:"
  kubectl -n default get endpointslices -l kubernetes.io/service-name=reviews \
    -o wide --context "$ctx" 2>/dev/null | sed 's/^/    /' || true
done

echo
echo "--- Envoy/istiod view (local pods + remote east-west gateway) ---"
for cl in 'outbound|9080||reviews.default.svc.cluster.local' \
          'outbound|9080|v1|reviews.default.svc.cluster.local' \
          'outbound|9080|v2|reviews.default.svc.cluster.local'; do
  echo "  ${cl}"
  istioctl -n default proxy-config endpoint "$POD1" --context "$CTX1" \
    --cluster "$cl" 2>/dev/null | sed 's/^/    /' || true
done

echo
echo "--- east-west gateway VIPs ---"
for ctx in "$CTX1" "$CTX2"; do
  echo "  ${ctx}: $(eastwest_ip "$ctx")"
done

echo
echo "INTERPRETATION: an endpoint of 10.244.x.x is a local mesh1 pod."
echo "An endpoint equal to the mesh2 east-west VIP on port 15443 is the bundled"
echo "representation of every mesh2 pod - traffic to it is SNI-routed across the"
echo "cluster boundary. If only 10.244.x.x appears, the remote secret is not syncing."

say "10. Live cross-cluster request test"
ensure_traffic_client "$CTX1"

PODS1="$(kubectl -n default get pods -l app=reviews --context "$CTX1" \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"
PODS2="$(kubectl -n default get pods -l app=reviews --context "$CTX2" \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"

echo "reviews pods in ${NAME1}:"
echo "$PODS1" | sed 's/^/  /'
echo "reviews pods in ${NAME2}:"
echo "$PODS2" | sed 's/^/  /'

echo
echo "sending 60 requests from a ${NAME1} pod to http://reviews:9080/reviews/0"
served="$(kubectl -n default exec traffic-client --context "$CTX1" -- sh -c '
  i=0
  while [ $i -lt 60 ]; do
    curl -s -m 5 http://reviews:9080/reviews/0
    echo
    i=$((i+1))
  done
' 2>/dev/null | sed -n 's/.*"podname": *"\([^"]*\)".*/\1/p')"

echo
echo "pods that answered (count  pod):"
echo "$served" | sort | uniq -c | sort -rn | sed 's/^/  /'

from1=0; from2=0; unknown=0
while IFS= read -r n; do
  [ -n "$n" ] || continue
  if echo "$PODS1" | grep -qx "$n"; then
    from1=$((from1+1))
  elif echo "$PODS2" | grep -qx "$n"; then
    from2=$((from2+1))
  else
    unknown=$((unknown+1))
  fi
done <<< "$served"
total=$((from1 + from2 + unknown))

echo
echo "routed to ${NAME1} pods: ${from1}/${total}"
echo "routed to ${NAME2} pods: ${from2}/${total}"
[ "$unknown" -gt 0 ] && echo "unmatched (curl error / no podname): ${unknown}"

echo
if [ "$from2" -gt 0 ] && [ "$from1" -gt 0 ]; then
  ok "requests from ${NAME1} were served by pods in BOTH clusters - cross-cluster routing works"
elif [ "$from2" -gt 0 ]; then
  ok "requests from ${NAME1} were served by ${NAME2} pods - cross-cluster routing works"
elif [ "$from1" -gt 0 ]; then
  warn "all requests were served locally; remote endpoints may not be syncing"
  istioctl remote-clusters --context "$CTX1" || true
else
  warn "no responses - check mTLS certificates and the reviews VirtualService"
fi

say "11. Ingress"
GW="$(ingress_ip "$CTX1")"
echo "ingress VIP: ${GW:-none}"
[ -n "$GW" ] && curl -s -o /dev/null -m 10 -w 'GET /productpage -> HTTP %{http_code}\n' "http://${GW}/productpage" || true

echo
echo "Evidence written to: ${OUT}"