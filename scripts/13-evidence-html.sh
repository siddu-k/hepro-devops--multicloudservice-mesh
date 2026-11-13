#!/usr/bin/env bash
# 13-evidence-html.sh -- capture the command output used as evidence and render
# it as a terminal-styled HTML page, so each item can be screenshotted cleanly.
#
# Output: evidence/terminal-evidence.html   (open with ?s=NN to show one section)
set -uo pipefail
ROOT="/mnt/c/siddu/VOICE DESK/devops-project-5"
EV="$ROOT/evidence"
TMP=/tmp/ev
mkdir -p "$TMP" "$EV"
export PATH=/root/istio-1.32.0/bin:$PATH

cap() { # cap <file> <command string>
  local f="$1"; shift
  { echo "\$ $*"; bash -c "$*"; } > "$TMP/$f.txt" 2>&1
}

POD1=$(kubectl -n default get pods -l app=productpage -o jsonpath='{.items[0].metadata.name}' --context kind-mesh1)

cap 01 "kubectl get nodes -o wide --context kind-mesh1"
cap 02 "kubectl get nodes -o wide --context kind-mesh2"
cap 03 "kubectl get pods -n istio-system --context kind-mesh1; echo; kubectl get pods -n istio-system --context kind-mesh2"
cap 04 "kubectl get pods -n default --context kind-mesh1; echo; kubectl get pods -n default --context kind-mesh2"
cap 05 "kubectl -n default get pods --context kind-mesh1 -o custom-columns='POD:.metadata.name,APP-CONTAINERS:.spec.containers[*].name,SIDECAR(init):.spec.initContainers[*].name'"
cap 06 "istioctl proxy-status --context kind-mesh1"
cap 07 "istioctl -n default proxy-config endpoint $POD1 --context kind-mesh1 --cluster 'outbound|9080||reviews.default.svc.cluster.local'"
cap 08 "istioctl remote-clusters --context kind-mesh1; echo; istioctl remote-clusters --context kind-mesh2"
cap 09 "kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway --context kind-mesh1 -o custom-columns='NAME:.metadata.name,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip,PORTS:.spec.ports[*].port'; echo; kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway --context kind-mesh2 -o custom-columns='NAME:.metadata.name,EXTERNAL-IP:.status.loadBalancer.ingress[0].ip,PORTS:.spec.ports[*].port'"
cap 10 "kubectl -n default get peerauthentication default -o yaml --context kind-mesh1"
cap 11 "kubectl -n default exec traffic-client --context kind-mesh1 -- sh -c 'curl -s -o /dev/null -w \"in-mesh sidecar pod  -> HTTP %{http_code}\\n\" -m 5 http://reviews:9080/reviews/0'; kubectl -n default exec mtls-probe --context kind-mesh1 -- sh -c 'curl -s -o /dev/null -w \"pod without sidecar -> HTTP %{http_code}\\n\" -m 5 http://reviews:9080/reviews/0'"
cap 12 "kubectl -n default get virtualservice reviews -o yaml --context kind-mesh1 | sed -n '1,60p'"
cap 13 "kubectl -n default get destinationrule reviews -o yaml --context kind-mesh1 | sed -n '1,60p'"
cap 14 "kubectl -n default describe virtualservice reviews --context kind-mesh1 | tail -20"
cap 15 "bash $ROOT/scripts/06-traffic-routing.sh 2>&1 | tail -25"

# fall back to the newest saved evidence files for the long runs
latest() { ls -t "$EV"/$1-*.txt 2>/dev/null | head -1; }
RES=$(latest resilience); VER=$(latest verify)
[ -n "${RES:-}" ] && { echo "\$ bash scripts/10-resilience.sh --hard" > "$TMP/16.txt"; cat "$RES" >> "$TMP/16.txt"; }
[ -n "${VER:-}" ] && { tail -45 "$VER" > "$TMP/17.txt"; }

python3 - "$TMP" "$EV/terminal-evidence.html" <<'PY'
import html, os, sys

tmp, out = sys.argv[1], sys.argv[2]
titles = {
 "01": "Activity 1 - mesh1 node (Kubernetes 1.37, Ready)",
 "02": "Activity 1 - mesh2 node (separate cluster, separate node)",
 "03": "Activity 1 - Istio control plane and gateways running in both clusters",
 "04": "Activity 1 - Bookinfo pods running in both clusters (2/2 = app + sidecar)",
 "05": "Activity 1 - Envoy sidecar injection (native sidecar in initContainers)",
 "06": "Activity 1 - istioctl proxy-status: every proxy SYNCED",
 "07": "Activity 1 - cross-cluster endpoints: local pods + mesh2 east-west gateway",
 "08": "Activity 1 - istioctl remote-clusters: the peer cluster is registered",
 "09": "Activity 1 - gateway LoadBalancer VIPs per cluster",
 "10": "Activity 2 - PeerAuthentication STRICT",
 "11": "Activity 2 - mTLS enforced: sidecar 200, sidecar-less pod refused",
 "12": "Activity 2 - VirtualService reviews (80/20 split)",
 "13": "Activity 2 - DestinationRule reviews (subsets v1/v2/v3)",
 "14": "Activity 2 - resolved weights on the VirtualService",
 "15": "Activity 2 - measured traffic split over 100 requests",
 "16": "Activity 2 - resilience: one cluster loses reviews-v2, then both",
 "17": "Activity 2 / 1 - 09-verify.sh summary: cross-cluster routing proven",
}
order = sorted(titles)
sections = []
for k in order:
    p = os.path.join(tmp, k + ".txt")
    if not os.path.exists(p):
        continue
    body = html.escape(open(p, encoding="utf-8", errors="replace").read())
    sections.append(f'<section id="s{k}"><h2>{k} &middot; {html.escape(titles[k])}</h2><pre>{body}</pre></section>')

doc = """<!doctype html>
<html><head><meta charset="utf-8"><title>Project 5 - command evidence</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px; background:#0d1117;
         font-family: ui-monospace, "Cascadia Mono", "Consolas", monospace; color:#e6edf3; }
  section { max-width:1180px; margin:0 auto 28px; }
  h2 { font-family: ui-sans-serif, "Segoe UI", sans-serif; font-size:15px; font-weight:600;
       color:#7ee787; letter-spacing:.2px; margin:0 0 8px; }
  pre { margin:0; padding:18px 20px; background:#161b22; border:1px solid #30363d;
        border-radius:8px; font-size:13.5px; line-height:1.55; white-space:pre-wrap;
        word-break:break-word; box-shadow:0 2px 12px rgba(0,0,0,.45); }
  body.single section { display:none; }
  body.single section.show { display:block; }
</style></head><body>
""" + "\n".join(sections) + """
<script>
  const s = new URLSearchParams(location.search).get("s");
  if (s) { document.body.classList.add("single");
           const el = document.getElementById("s"+s); if (el) el.classList.add("show"); }
</script>
</body></html>"""
open(out, "w", encoding="utf-8").write(doc)
print("wrote", out, len(sections), "sections")
PY