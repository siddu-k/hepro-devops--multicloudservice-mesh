#!/usr/bin/env bash
# 06-traffic-routing.sh -- 80/20 split between reviews v1 and v2, then measure it.
#
# The measurement is the point: 100 requests, count how many responses carry a
# "rating" field. v1 has no rating, v2 does, so the ratio should land near 20/80.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
init

say "Applying DestinationRule + VirtualService (both clusters)"
# Applied to both so the rule holds regardless of which cluster serves the pod.
for ctx in "$CTX1" "$CTX2"; do
  kubectl apply -f "${ROOT}/yaml/reviews-destination-rule.yaml" --context "$ctx"
  kubectl apply -f "${ROOT}/yaml/reviews-virtual-service.yaml" --context "$ctx"
done

say "Configured rules"
for ctx in "$CTX1" "$CTX2"; do
  echo "--- ${ctx} ---"
  kubectl get destinationrule,virtualservice -n default --context "$ctx"
done
kubectl describe virtualservice reviews -n default --context "$CTX1" | sed -n '1,40p'

say "Measuring the split with 100 requests"
ensure_traffic_client "$CTX1"

# Classification is done on the pod name in the response body, not on whether a
# "rating" field is present: v3 also returns a rating, so a field-based check
# would count v3 as v2. Non-200 responses are counted as failures instead of
# being silently folded into v1.
result="$(kubectl -n default exec traffic-client --context "$CTX1" -- sh -c '
  v1=0; v2=0; v3=0; fail=0; i=0
  while [ $i -lt 100 ]; do
    out=$(curl -s -m 5 -w "|%{http_code}" http://reviews:9080/reviews/0) || { fail=$((fail+1)); i=$((i+1)); continue; }
    code=${out##*|}; body=${out%|*}
    if [ "$code" != "200" ]; then
      fail=$((fail+1))
    else
      case "$body" in
        *reviews-v1*) v1=$((v1+1)) ;;
        *reviews-v2*) v2=$((v2+1)) ;;
        *reviews-v3*) v3=$((v3+1)) ;;
        *)            fail=$((fail+1)) ;;
      esac
    fi
    i=$((i+1))
  done
  echo "v1=$v1 v2=$v2 v3=$v3 fail=$fail"
')"
echo "  ${result}"

v1="$(echo "$result" | sed -n 's/.*v1=\([0-9]*\).*/\1/p')"
v2="$(echo "$result" | sed -n 's/.*v2=\([0-9]*\).*/\1/p')"
v3="$(echo "$result" | sed -n 's/.*v3=\([0-9]*\).*/\1/p')"
fail="$(echo "$result" | sed -n 's/.*fail=\([0-9]*\).*/\1/p')"
v1="${v1:-0}"; v2="${v2:-0}"; v3="${v3:-0}"; fail="${fail:-0}"
echo
if [ "$v2" -gt 0 ] && [ "$v3" -eq 0 ] && [ "$fail" -eq 0 ]; then
  ok "split is working: v1=${v1}% v2=${v2}% (target 80:20), v3 not selected, no failures"
elif [ "$v2" -gt 0 ] && [ "$v1" -gt 0 ]; then
  warn "both v1 and v2 served ${v1}/${v2}, but check v3=${v3} fail=${fail} against the 80:20 weights"
  warn "if v3 is non-zero, an older VirtualService still routes to it"
else
  warn "only one subset responded - run: istioctl proxy-config endpoint <pod> --cluster 'outbound|9080|v2|reviews.default.svc.cluster.local'"
fi

cat <<EOF

Sample responses:
  v1 -> {"id":"0","podname":"reviews-v1-...","clustername":"..."}
  v2 -> {...,"rating":{"stars":5,"color":"black"}}

Evidence to capture:
  kubectl get virtualservice,destinationrule -n default --context ${CTX1}
  kubectl describe virtualservice reviews -n default --context ${CTX1}
  the v1/v2 counts above

Next: ./scripts/07-addons.sh
EOF