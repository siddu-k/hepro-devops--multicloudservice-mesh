#!/usr/bin/env bash
# 10-resilience.sh -- controlled failure test across the cluster boundary.
#
# What is tested
#   reviews-v2 runs in BOTH clusters. The VirtualService sends 20% of traffic to
#   subset v2. This script deletes the v2 pods in mesh2 only, then measures
#   whether the 20% share of traffic survives.
#
# Expected outcome, and why it matters
#   Because the same subset also exists in mesh1, requests for v2 are re-routed
#   to mesh1's v2 pod through the local cluster - the subset ratio is preserved
#   and there are no user-visible errors. That is cross-cluster resilience
#   working through service discovery, not a hard-coded failover policy.
#
#   This is deliberately NOT the same as "the cluster died": if reviews-v2 were
#   removed from both clusters, the 20% share would have no destination and the
#   requests would fail. Both facts belong in the report.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="${ROOT}/evidence"
mkdir -p "$OUTDIR"
OUT="${OUTDIR}/resilience-${STAMP}.txt"
exec > >(tee -a "$OUT") 2>&1

REQUESTS="${REQUESTS:-30}"

say "Baseline: ${REQUESTS} requests, mesh2 healthy"
ensure_traffic_client "$CTX1"

measure() {
  local label="$1"
  local out ok bad v1 v2 v3
  out="$(kubectl -n default exec traffic-client --context "$CTX1" -- sh -c "
    ok=0; bad=0; v1=0; v2=0; v3=0; i=0
    while [ \$i -lt ${REQUESTS} ]; do
      r=\$(curl -s -m 5 -w '|%{http_code}' http://reviews:9080/reviews/0)
      code=\${r##*|}; body=\${r%|*}
      if [ \"\$code\" = \"200\" ]; then
        ok=\$((ok+1))
        case \"\$body\" in
          *reviews-v1*) v1=\$((v1+1)) ;;
          *reviews-v2*) v2=\$((v2+1)) ;;
          *reviews-v3*) v3=\$((v3+1)) ;;
        esac
      else
        bad=\$((bad+1))
      fi
      i=\$((i+1))
    done
    echo \"\$ok \$bad \$v1 \$v2 \$v3\"
  ")"
  read -r ok bad v1 v2 v3 <<< "$out"
  printf '  %-22s ok=%-3s fail=%-3s  v1=%-3s v2=%-3s v3=%-3s\n' "$label" "$ok" "$bad" "$v1" "$v2" "$v3"
  M_OK="$ok"; M_BAD="$bad"; M_V2="$v2"
}

served_pods() {
  kubectl -n default exec traffic-client --context "$CTX1" -- sh -c '
    i=0
    while [ $i -lt 20 ]; do
      curl -s -m 5 http://reviews:9080/reviews/0
      echo
      i=$((i+1))
    done
  ' 2>/dev/null | sed -n 's/.*"podname": *"\([^"]*\)".*/\1/p' | sort | uniq -c
}

measure "baseline"
BASE_OK="$M_OK"; BASE_BAD="$M_BAD"

V2_PODS_2="$(kubectl -n default get pods -l app=reviews,version=v2 --context "$CTX2" \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"
echo "  mesh2 reviews-v2 pods: $(echo "$V2_PODS_2" | tr '\n' ' ')"

say "Failure injection: scaling reviews-v2 to 0 in ${NAME2}"
kubectl -n default scale deployment/reviews-v2 --replicas=0 --context "$CTX2"
kubectl -n default wait --for=delete pod \
  -l app=reviews,version=v2 --context "$CTX2" --timeout=180s >/dev/null 2>&1 || true
kubectl -n default get pods -l app=reviews --context "$CTX2"

say "During the failure"
sleep 5
measure "mesh2 v2 removed"
DUR_OK="$M_OK"; DUR_BAD="$M_BAD"; DUR_V2="$M_V2"

echo
echo "  which pods answered during the outage:"
served_pods | sed 's/^/    /'

echo
v2_from_2=0
while IFS= read -r line; do
  [ -n "$line" ] || continue
  pod="${line##* }"
  if echo "$V2_PODS_2" | grep -qx "$pod"; then v2_from_2=$((v2_from_2+1)); fi
done < <(served_pods)
if [ "$v2_from_2" -eq 0 ]; then
  ok "no ${NAME2} reviews-v2 pod answered - the outage is real"
else
  warn "a ${NAME2} reviews-v2 pod still answered - the deployment was not fully removed"
fi

say "Restoring reviews-v2 in ${NAME2}"
kubectl -n default scale deployment/reviews-v2 --replicas=1 --context "$CTX2"
kubectl -n default rollout status deployment/reviews-v2 --context "$CTX2" --timeout=300s >/dev/null
sleep 8
measure "restored"
AFT_OK="$M_OK"; AFT_BAD="$M_BAD"

echo
echo "================ RESULT ================"
printf 'baseline (both clusters up)        ok=%s fail=%s\n' "$BASE_OK" "$BASE_BAD"
printf 'during  (mesh2 v2 scaled to 0)    ok=%s fail=%s  v2_served=%s\n' "$DUR_OK" "$DUR_BAD" "$DUR_V2"
printf 'after   (mesh2 v2 restored)       ok=%s fail=%s\n' "$AFT_OK" "$AFT_BAD"
echo

if [ "$DUR_BAD" -eq 0 ] && [ "$DUR_V2" -gt 0 ]; then
  ok "the v2 share survived the loss of ${NAME2}'s v2 pods"
  echo "  The 20% v2 traffic was served by ${NAME1}'s reviews-v2 instead. Service"
  echo "  discovery across the mesh provided the failover: no requests failed and"
  echo "  the percentage split was preserved."
elif [ "$DUR_BAD" -gt 0 ]; then
  warn "requests failed while the remote v2 pods were gone"
  echo "  This would be the expected result if reviews-v2 had been removed from"
  echo "  BOTH clusters: the 20% v2 share has no destination, and there is no"
  echo "  outlierDetection / locality-failover policy to absorb it."
else
  warn "no v2 responses during the outage - check the VirtualService weights"
fi

cat <<EOF

What the dashboards show during the outage:
  Kiali      - the ${NAME2} reviews-v2 node drops out of the graph
  Grafana    - istio_requests_total for that workload stops increasing
  Prometheus - sum(rate(istio_requests_total{destination_workload="reviews-v2"}[1m])) by (source_cluster)

Screenshot: kubectl get pods -l app=reviews --context ${CTX2} while v2 is at 0.
EOF

# ---------------------------------------------------------------- hard failure
# Optional second experiment: remove the subset from BOTH clusters, so there is
# no healthy destination for the 20% share at all.
if [ "${1:-}" = "--hard" ]; then
  say "HARD FAILURE: removing reviews-v2 from BOTH clusters"
  for ctx in "$CTX1" "$CTX2"; do
    kubectl -n default scale deployment/reviews-v2 --replicas=0 --context "$ctx" >/dev/null
    kubectl -n default wait --for=delete pod \
      -l app=reviews,version=v2 --context "$ctx" --timeout=180s >/dev/null 2>&1 || true
  done

  echo "  reviews pods still running:"
  for ctx in "$CTX1" "$CTX2"; do
    echo "    ${ctx}:"
    kubectl -n default get pods -l app=reviews --context "$ctx" --no-headers \
      | awk '{print "      " $1}' || true
  done

  echo
  measure "v2 removed everywhere"
  HARD_OK="$M_OK"; HARD_BAD="$M_BAD"

  say "Restoring reviews-v2 in both clusters"
  for ctx in "$CTX1" "$CTX2"; do
    kubectl -n default scale deployment/reviews-v2 --replicas=1 --context "$ctx" >/dev/null
    kubectl -n default rollout status deployment/reviews-v2 --context "$ctx" --timeout=300s >/dev/null
  done
  sleep 8
  measure "fully restored"

  echo
  echo "============== HARD FAILURE RESULT =============="
  printf 'v2 absent from both clusters   ok=%s fail=%s  (v2 had no destination)\n' "$HARD_OK" "$HARD_BAD"
  printf 'after restoring v2 everywhere  ok=%s fail=%s\n' "$M_OK" "$M_BAD"
  echo
  if [ "${HARD_BAD:-0}" -gt 0 ]; then
    ok "failure behaviour observed and explained: the 20% subset had no endpoints"
    echo "  Requests routed to subset v2 failed while no v2 pod existed anywhere."
    echo "  This is the honest limit of the configuration: Istio does not silently"
    echo "  fall back to v1 without a failover policy (outlierDetection, or a"
    echo "  VirtualService fallback route). With both clusters healthy again the"
    echo "  split is restored, proving the failure was the missing destination"
    echo "  rather than a broken mesh."
  else
    warn "no failures even with v2 absent everywhere - check the VirtualService"
  fi
fi