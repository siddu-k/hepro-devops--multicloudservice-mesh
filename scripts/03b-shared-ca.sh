#!/usr/bin/env bash
# 03b-shared-ca.sh -- give both clusters the SAME root of trust.
#
# WHY THIS IS MANDATORY
# ---------------------
# By default each istiod generates its own self-signed root CA. That is fine
# inside one cluster, but across two clusters it means a pod in mesh1 presents
# a certificate signed by CA-A while the pod in mesh2 only trusts CA-B. The
# TLS handshake fails and you get 503s that look like a networking problem.
# Istio's multicluster documentation requires a shared root of trust for
# exactly this reason.
#
# This installs Istio's own sample "plugin CA" certificate material into a
# `cacerts` secret in both clusters, then restarts istiod and the workloads so
# every proxy is re-issued a certificate from the shared CA.
#
# WARNING: samples/certs are published test certificates. Never use them
# outside a lab. In production you generate your own root + intermediate.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

CERTDIR="${ISTIO_DIR}/samples/certs"
[ -f "${CERTDIR}/root-cert.pem" ] || die "missing ${CERTDIR}/root-cert.pem"

say "Root certificate both clusters will trust"
openssl x509 -in "${CERTDIR}/root-cert.pem" -noout -subject -issuer -dates 2>/dev/null || true

for ctx in "$CTX1" "$CTX2"; do
  say "Installing shared cacerts on ${ctx}"
  kubectl create secret generic cacerts -n istio-system --context "$ctx" \
    --from-file=ca-cert.pem="${CERTDIR}/ca-cert.pem" \
    --from-file=ca-key.pem="${CERTDIR}/ca-key.pem" \
    --from-file=root-cert.pem="${CERTDIR}/root-cert.pem" \
    --from-file=cert-chain.pem="${CERTDIR}/cert-chain.pem" \
    --dry-run=client -o yaml | kubectl apply -f - --context "$ctx" >/dev/null
  ok "secret/cacerts"

  # istiod only reads cacerts at startup
  say "Restarting istiod on ${ctx} so it uses the shared CA"
  kubectl -n istio-system rollout restart deployment/istiod --context "$ctx" >/dev/null
  kubectl -n istio-system rollout status deployment/istiod --context "$ctx" --timeout=300s
  ok "istiod restarted"

  # The gateways are Envoy proxies too. They also hold a certificate issued by
  # the CA that was active when they started, so without this they keep
  # presenting an untrusted certificate and every ingress request returns 503.
  say "Restarting the gateways on ${ctx} so they get certificates from the shared CA"
  for gw in istio-ingressgateway istio-eastwestgateway; do
    kubectl -n istio-system rollout restart deployment/"$gw" --context "$ctx" >/dev/null 2>&1 || true
    kubectl -n istio-system rollout status deployment/"$gw" --context "$ctx" --timeout=300s >/dev/null 2>&1 || true
  done
  ok "gateways restarted"

  say "Restarting workloads on ${ctx} so proxies get certificates from the shared CA"
  kubectl -n default rollout restart deployment --context "$ctx" >/dev/null 2>&1 || true
  kubectl -n default rollout status deployment --context "$ctx" --timeout=300s >/dev/null 2>&1 || true
  ok "workloads restarted"
done

say "Waiting for sidecars to reconnect"
sleep 10

say "Certificate issuers now in use (both must match)"
for ctx in "$CTX1" "$CTX2"; do
  pod="$(kubectl -n default get pods -l app=reviews -o jsonpath='{.items[0].metadata.name}' --context "$ctx")"
  echo "--- ${ctx} ${pod} ---"
  istioctl -n default proxy-config secret "$pod" --context "$ctx" 2>/dev/null \
    | grep -E 'default|ROOTCA|Active' | head -5 || true
done

cat <<EOF

Both clusters now issue certificates from the same root, which is what makes
mutual TLS work ACROSS the cluster boundary rather than only inside one cluster.

Verify the two ROOTCA serial numbers above are identical.

Next: ./scripts/06-traffic-routing.sh
EOF