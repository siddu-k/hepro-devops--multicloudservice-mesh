#!/usr/bin/env bash
# 08-generate-traffic.sh -- drive real requests so the dashboards have data.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

GW="$(ingress_ip "$CTX1")"
[ -n "$GW" ] || die "no ingress VIP on ${CTX1} yet"
ok "gateway http://${GW}"

say "Warming up"
code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "http://${GW}/productpage" || true)"
echo "  /productpage -> HTTP ${code:-no-response}"
[ "$code" = "200" ] || die "gateway is not serving /productpage; is bookinfo-gateway applied?"

say "Sending 100 requests"
ok_count=0; other=0
for i in $(seq 1 100); do
  c="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://${GW}/productpage" || true)"
  if [ "$c" = "200" ]; then ok_count=$((ok_count+1)); else other=$((other+1)); fi
done
echo "  200=${ok_count}  non-200=${other}"

say "Last response, first lines"
curl -s -m 10 "http://${GW}/productpage" | grep -iE 'reviews|stars|Reviews' | head -5 || true

cat <<EOF

Traffic generated. Give Prometheus ~30s to scrape, then:

  istioctl dashboard kiali --context ${CTX1}        -> Graph, namespace "default"
  istioctl dashboard grafana --context ${CTX1}      -> Istio Mesh dashboard
  istioctl dashboard prometheus --context ${CTX1}

Useful PromQL:
  sum(rate(istio_requests_total[1m])) by (destination_service_name)
  histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket[5m])) by (le))

Screenshots for the report:
  1. Kiali service graph (default namespace, traffic visible)
  2. Grafana Istio Mesh dashboard
  3. Prometheus query result
  4. Jaeger trace of a /productpage request

Next: ./scripts/09-verify.sh
EOF