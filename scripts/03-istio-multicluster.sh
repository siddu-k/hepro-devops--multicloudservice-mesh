#!/usr/bin/env bash
# 03-istio-multicluster.sh -- join both clusters into ONE Istio mesh.
#
# Topology: MULTI-PRIMARY, MULTI-NETWORK
#   mesh1 = control plane + east-west gateway, network1
#   mesh2 = control plane + east-west gateway, network2
#   each receives a remote secret for the other, so endpoints cross-register
#   pod traffic between clusters MUST pass through the east-west gateways,
#   because the two pod CIDRs have no route between them.
#
# Both gateways are declared in ONE IstioOperator per cluster. If you install
# the control plane and the east-west gateway as two separate istioctl runs,
# the second run is pruned away by the first on the next invocation - which is
# exactly the trap this script avoids.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

MESH_ID="mesh1"
NET1="network1"; NET2="network2"

say "Waiting for any stale east-west state to settle"
for ctx in "$CTX1" "$CTX2"; do
  kubectl -n istio-system delete deployment istio-eastwestgateway \
    --ignore-not-found --context "$ctx" >/dev/null 2>&1 || true
done

install_mesh_node() {
  local ctx="$1" name="$2" net="$3"

  say "Installing control plane + both gateways on ${ctx} (clusterName=${name}, network=${net})"
  kubectl create namespace istio-system --context "$ctx" \
    --dry-run=client -o yaml | kubectl apply -f - --context "$ctx" >/dev/null
  kubectl label namespace istio-system "topology.istio.io/network=${net}" \
    --context "$ctx" --overwrite >/dev/null

  istioctl install --context "$ctx" -y -f - <<EOF
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  profile: default
  meshConfig:
    # Tells istiod where the tracing backend (Jaeger) lives. The Telemetry
    # resource applied in 07-addons.sh then switches tracing on and sets the
    # sampling rate; without this provider entry the proxies have nowhere to
    # send spans and Jaeger stays empty.
    extensionProviders:
      - name: jaeger
        zipkin:
          service: jaeger-collector.istio-system.svc.cluster.local
          port: 9411
  components:
    ingressGateways:
      - name: istio-ingressgateway
        enabled: true
      - name: istio-eastwestgateway
        enabled: true
        label:
          istio: eastwestgateway
          app: istio-eastwestgateway
          topology.istio.io/network: ${net}
        k8s:
          env:
            - name: ISTIO_META_REQUESTED_NETWORK_VIEW
              value: ${net}
          service:
            ports:
              - name: status-port
                port: 15021
                targetPort: 15021
              - name: tls
                port: 15443
                targetPort: 15443
              - name: tls-istiod
                port: 15012
                targetPort: 15012
              - name: tls-webhook
                port: 15017
                targetPort: 15017
  values:
    global:
      meshID: ${MESH_ID}
      multiCluster:
        clusterName: ${name}
      network: ${net}
    gateways:
      istio-ingressgateway:
        injectionTemplate: gateway
    pilot:
      traceSampling: 100.0
EOF

  say "Waiting for the east-west LoadBalancer VIP on ${ctx}"
  local i vip=""
  for i in $(seq 1 90); do
    vip="$(kubectl -n istio-system get svc istio-eastwestgateway --context "$ctx" \
           -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
    [ -n "$vip" ] && break
    sleep 2
  done
  [ -n "$vip" ] || die "east-west gateway never got a VIP on ${ctx}"
  ok "east-west VIP ${vip} on ${name}"

  say "Exposing services through the east-west gateway on ${ctx}"
  kubectl apply -n istio-system \
    -f "${ISTIO_DIR}/samples/multicluster/expose-services.yaml" \
    --context "$ctx" >/dev/null
  ok "istiod / ingress / egress exposed via SNI"
}

install_mesh_node "$CTX1" "$NAME1" "$NET1"
install_mesh_node "$CTX2" "$NAME2" "$NET2"

# ------------------------------------------------------- cross-cluster secrets
# kind publishes the apiserver on 127.0.0.1:<random>, useless inside a pod.
# Point the remote secret at the node's underlay address, which is in the
# apiserver certificate SANs.
say "Exchanging remote secrets (this is what makes the clusters share endpoints)"
istioctl create-remote-secret --context "$CTX1" --name "$NAME1" \
  --server "https://$(underlay_ip "${NAME1}-control-plane"):6443" \
  | kubectl apply -f - --context "$CTX2"
istioctl create-remote-secret --context "$CTX2" --name "$NAME2" \
  --server "https://$(underlay_ip "${NAME2}-control-plane"):6443" \
  | kubectl apply -f - --context "$CTX1"

# Docker hands out bridge IPs in start order, so after a reboot the node that
# used to be 172.30.0.2 can come back as 172.30.0.3. An existing secret then
# points at the WRONG node (usually its own), istiod reports `timeout` and
# cross-cluster load balancing silently stops. Re-point both secrets at the
# address the peer has right now.
say "Reconciling remote secrets with the current node addresses"
reconcile_secret() { # <ctx holding the secret> <secret> <data key> <correct ip>
  local ctx=$1 sec=$2 key=$3 ip=$4 cur
  kubectl -n istio-system get secret "$sec" --context "$ctx" \
    -o jsonpath="{.data.${key}}" | base64 -d > /tmp/sec.yaml
  cur=$(grep -oE 'server: https://[0-9.]+:6443' /tmp/sec.yaml | head -1 \
        | grep -oE '([0-9]+\.){3}[0-9]+')
  if [ "$cur" = "$ip" ]; then
    ok "${sec} already points at ${ip}"
    return
  fi
  warn "${sec} points at ${cur}, repointing to ${ip}"
  sed -i "s#server: https://${cur}:6443#server: https://${ip}:6443#" /tmp/sec.yaml
  python3 - "$key" <<'PY'
import base64, json, sys
raw = open("/tmp/sec.yaml", "rb").read()
json.dump({"data": {sys.argv[1]: base64.b64encode(raw).decode()}},
          open("/tmp/sec-patch.json", "w"))
PY
  kubectl -n istio-system patch secret "$sec" --context "$ctx" \
    --type merge --patch-file /tmp/sec-patch.json >/dev/null
  ok "patched ${sec}"
}
reconcile_secret "$CTX1" istio-remote-secret-${NAME2} "$NAME2" \
  "$(underlay_ip "${NAME2}-control-plane")"
reconcile_secret "$CTX2" istio-remote-secret-${NAME1} "$NAME1" \
  "$(underlay_ip "${NAME1}-control-plane")"

say "Waiting for control planes"
for ctx in "$CTX1" "$CTX2"; do
  kubectl -n istio-system wait --for=condition=Ready pod \
    -l app=istiod --context "$ctx" --timeout=300s >/dev/null
done
ok "both istiod pods ready"

# --------------------------------------------------------------------- verify
say "Remote cluster view"
istioctl remote-clusters --context "$CTX1"
istioctl remote-clusters --context "$CTX2"

say "Control plane / gateway pods"
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl get pods -n istio-system --context "$ctx"
done

say "Gateway addresses"
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway \
    --context "$ctx" -o custom-columns='NAME:.metadata.name,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip,PORTS:.spec.ports[*].port'
done

say "Proxy sync status"
istioctl proxy-status --context "$CTX1" || true

cat <<EOF

Mesh is up.

  ${NAME1}: istiod + ingress + east-west gateway, network ${NET1}
  ${NAME2}: istiod + ingress + east-west gateway, network ${NET2}

Expected: 'istioctl remote-clusters' lists the peer cluster in each.
Expected: proxy-status shows SYNCED for every gateway proxy.

Next: ./scripts/04-bookinfo.sh
EOF