#!/usr/bin/env bash
# 05-mtls.sh -- enforce STRICT mutual TLS, then PROVE it.
#
# The PDF only asks you to describe the policy. A policy screenshot alone
# proves nothing, so this script also runs a negative test: a pod with the
# sidecar disabled must be unable to reach a mesh service once STRICT is on.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

say "Applying STRICT PeerAuthentication to both clusters"
for ctx in "$CTX1" "$CTX2"; do
  kubectl apply -f "${ROOT}/yaml/peer-authentication.yaml" --context "$ctx"
done

say "Waiting for the policy to propagate"
sleep 8

say "Policy state"
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl get peerauthentication -n default --context "$ctx"
  kubectl describe peerauthentication default -n default --context "$ctx" | sed -n '1,14p'
done

say "Positive test: in-mesh pod -> reviews (mTLS auto-upgraded)"
ensure_traffic_client "$CTX1"
code_mesh="$(kubectl -n default exec traffic-client --context "$CTX1" -- \
  curl -s -o /dev/null -m 10 -w '%{http_code}' http://reviews:9080/reviews/0 || true)"
echo "  in-mesh request  -> HTTP ${code_mesh:-no-response}"

say "Negative test: pod WITHOUT sidecar -> reviews (must be rejected)"
kubectl -n default delete pod mtls-probe --ignore-not-found --context "$CTX1" >/dev/null 2>&1 || true
cat <<'EOF' | kubectl apply -f - --context "$CTX1" >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: mtls-probe
  namespace: default
  annotations:
    sidecar.istio.io/inject: "false"
  labels:
    app: mtls-probe
spec:
  containers:
  - name: curl
    image: curlimages/curl:8.10.1
    command: ["sleep", "3600"]
EOF
kubectl -n default wait --for=condition=Ready pod/mtls-probe --context "$CTX1" --timeout=240s >/dev/null
code_plain="$(kubectl -n default exec mtls-probe --context "$CTX1" -- \
  curl -s -o /dev/null -m 10 -w '%{http_code}' http://reviews:9080/reviews/0 || true)"
echo "  plaintext request -> HTTP ${code_plain:-no-response} (000/reset = rejected by STRICT)"

echo
if [ "${code_mesh}" = "200" ] && [ "${code_plain}" != "200" ]; then
  ok "mTLS proven: sidecar traffic 200, sidecar-less traffic blocked"
else
  warn "unexpected result - check that both clusters have sidecars and STRICT is applied"
  warn "mesh=${code_mesh:-none} plain=${code_plain:-none}"
fi

cat <<EOF

Evidence to capture:
  kubectl get peerauthentication -n default --context ${CTX1}
  kubectl describe peerauthentication default -n default --context ${CTX1}
  the negative test output above (plaintext refused)

Note: STRICT breaks anything that speaks plaintext into the namespace, including
kubelet probes. If a workload has probes, add port-level mTLS exemptions.

Next: ./scripts/06-traffic-routing.sh
EOF