#!/usr/bin/env bash
# Drive continuous traffic through mesh1's ingress so the dashboards have data.
GW=$(kubectl -n istio-system get svc istio-ingressgateway --context kind-mesh1 \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "generating traffic through http://${GW}/productpage"
for i in $(seq 1 900); do
  curl -s -o /dev/null -m 5 "http://${GW}/productpage"
  sleep 1
done
echo "traffic generation finished"