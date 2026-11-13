#!/usr/bin/env bash
# 07-addons.sh -- Prometheus, Grafana, Kiali, Jaeger on the primary cluster.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

ADDONS="${ISTIO_DIR}/samples/addons"

say "Installing monitoring / observability add-ons on ${CTX1}"
for f in prometheus grafana kiali jaeger; do
  if [ -f "${ADDONS}/${f}.yaml" ]; then
    kubectl apply -f "${ADDONS}/${f}.yaml" --context "$CTX1" >/dev/null
    ok "${f}"
  else
    warn "${f}.yaml not present in this Istio release - skipped"
  fi
done

say "Waiting for rollouts"
for d in prometheus grafana kiali; do
  if kubectl -n istio-system get deployment "$d" --context "$CTX1" >/dev/null 2>&1; then
    kubectl -n istio-system rollout status "deployment/${d}" --context "$CTX1" --timeout=300s
  fi
done
if kubectl -n istio-system get deployment jaeger --context "$CTX1" >/dev/null 2>&1; then
  kubectl -n istio-system rollout status deployment/jaeger --context "$CTX1" --timeout=300s
fi

say "Observability stack"
kubectl -n istio-system get pods --context "$CTX1" | grep -Ei 'prometheus|grafana|kiali|jaeger' || true
kubectl -n istio-system get svc --context "$CTX1" | grep -Ei 'prometheus|grafana|kiali|jaeger' || true

# ---------------------------------------------------------------- tracing setup
# Two separate things are needed for Jaeger to show anything:
#   1. the extension provider in meshConfig (done in 03-istio-multicluster.sh)
#   2. a Telemetry resource that switches tracing on for the workloads
# The Istio sample Jaeger deployment serves its UI under /jaeger, which its own
# router does not handle correctly; switching base_path to / makes the UI load
# at http://localhost:16686/ with a working search page.
say "Enabling distributed tracing (Telemetry resource on both clusters)"
for ctx in "$CTX1" "$CTX2"; do
  cat <<'EOF' | kubectl apply -f - --context "$ctx" >/dev/null
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: mesh-default
  namespace: istio-system
spec:
  tracing:
  - providers:
    - name: jaeger
    randomSamplingPercentage: 100.0
EOF
  ok "Telemetry/mesh-default on ${ctx}"
done

if kubectl -n istio-system get cm jaeger --context "$CTX1" >/dev/null 2>&1; then
  say "Pointing the Jaeger UI at / (the sample manifest uses /jaeger)"
  kubectl -n istio-system get cm jaeger --context "$CTX1" \
    -o jsonpath='{.data.config\.yaml}' > /tmp/jaeger-cm.yaml
  sed -i 's#base_path: /jaeger#base_path: /#' /tmp/jaeger-cm.yaml
  python3 - <<'PY'
import json
cfg = open("/tmp/jaeger-cm.yaml").read()
open("/tmp/jaeger-patch.json", "w").write(json.dumps({"data": {"config.yaml": cfg}}))
PY
  kubectl -n istio-system patch cm jaeger --context "$CTX1" \
    --type merge --patch-file /tmp/jaeger-patch.json >/dev/null
  kubectl -n istio-system rollout restart deployment/jaeger --context "$CTX1" >/dev/null
  kubectl -n istio-system rollout status deployment/jaeger --context "$CTX1" --timeout=300s >/dev/null
  ok "jaeger ui base path = /"
fi

say "Restarting proxies so the tracer is part of their bootstrap"
for ctx in "$CTX1" "$CTX2"; do
  kubectl -n default rollout restart deployment --context "$ctx" >/dev/null 2>&1 || true
  kubectl -n istio-system rollout restart deployment/istio-ingressgateway --context "$ctx" >/dev/null 2>&1 || true
  kubectl -n istio-system rollout restart deployment/istio-eastwestgateway --context "$ctx" >/dev/null 2>&1 || true
done
for ctx in "$CTX1" "$CTX2"; do
  kubectl -n default rollout status deployment --context "$ctx" --timeout=300s >/dev/null 2>&1 || true
done
ok "workloads and gateways restarted"

cat <<EOF

Dashboards (each command blocks and opens a browser; Ctrl-C to stop):

  istioctl dashboard kiali      --context ${CTX1}
  istioctl dashboard grafana    --context ${CTX1}
  istioctl dashboard prometheus --context ${CTX1}
  istioctl dashboard jaeger     --context ${CTX1}

These use kubectl port-forward under the hood, so they work from WSL.
If the browser does not open, the command prints a http://localhost:PORT URL -
paste it into the Windows browser.

Note: the add-ons are installed on ${CTX1} only. That is why Kiali will show the
${NAME1} graph; ${NAME2} workloads appear once cross-cluster endpoints are
resolved, which is what 09-verify.sh checks.

Next: ./scripts/08-generate-traffic.sh
EOF