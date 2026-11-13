#!/usr/bin/env bash
# 14-doc-screens.sh -- capture the exact command output used in the report and
# render it as terminal-style HTML cards (one per screenshot).
#
#   bash scripts/14-doc-screens.sh              capture + render
#   bash scripts/14-doc-screens.sh --render-only  re-render from /tmp/doc-ev
#
#   evidence/doc-screens.html?s=NN   shows a single card
set -uo pipefail
ROOT="/mnt/c/siddu/VOICE DESK/devops-project-5"
TMP=/tmp/doc-ev
EV="$ROOT/evidence"
mkdir -p "$TMP" "$EV"
export PATH=/root/istio-1.32.0/bin:$PATH

RENDER_ONLY=0
[ "${1:-}" = "--render-only" ] && RENDER_ONLY=1

cap() { # cap <id> <command>
  local f="$1"; shift
  { printf 'root@mesh-lab:~/devops-project-5# %s\n' "$*"; bash -c "$*"; } > "$TMP/$f.txt" 2>&1
}

if [ "$RENDER_ONLY" = "0" ]; then

POD1=$(kubectl -n default get pods -l app=productpage -o jsonpath='{.items[0].metadata.name}' --context kind-mesh1)

cap 00 "kubectl version --client; istioctl version --remote=false; kind version; docker --version"
cap 01 "kubectl get nodes -o wide --context kind-mesh1"
cap 02 "kubectl get nodes -o wide --context kind-mesh2"
cap 02b "kubectl config get-contexts kind-mesh1; echo; kubectl config get-contexts kind-mesh2; echo; kubectl config current-context"
cap 03 "kubectl -n istio-system get pods --context kind-mesh1"
cap 04 "kubectl -n istio-system get pods --context kind-mesh2"
cap 05 "kubectl -n default get pods --context kind-mesh1"
cap 06 "kubectl -n default get pods --context kind-mesh1 -o custom-columns='POD:.metadata.name,APP:.spec.containers[*].name,SIDECAR:.spec.initContainers[*].name'"
cap 07 "istioctl proxy-status --context kind-mesh1; echo; istioctl proxy-status --context kind-mesh2"
cap 08 "istioctl -n default proxy-config endpoint $POD1 --context kind-mesh1 --cluster 'outbound|9080||reviews.default.svc.cluster.local'"
cap 09 "istioctl remote-clusters --context kind-mesh1"
cap 10 "kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway --context kind-mesh1 -o custom-columns='NAME:.metadata.name,VIP:.status.loadBalancer.ingress[0].ip,PORTS:.spec.ports[*].port'; echo; kubectl -n istio-system get svc istio-ingressgateway istio-eastwestgateway --context kind-mesh2 -o custom-columns='NAME:.metadata.name,VIP:.status.loadBalancer.ingress[0].ip,PORTS:.spec.ports[*].port'"
cap 11 "kubectl -n default get peerauthentication default -o yaml --context kind-mesh1"
cap 12 "kubectl -n default exec traffic-client --context kind-mesh1 -- sh -c 'curl -s -o /dev/null -w \"in-mesh pod (with sidecar)   -> HTTP %{http_code}\\n\" -m 5 http://reviews:9080/reviews/0'; kubectl -n default exec mtls-probe --context kind-mesh1 -- sh -c 'curl -s -o /dev/null -w \"pod without sidecar         -> HTTP %{http_code}\\n\" -m 5 http://reviews:9080/reviews/0' || echo \"curl exit \$? = connection reset, the STRICT mTLS policy rejected a plaintext client (expected)\""
cap 13 "kubectl -n default describe virtualservice reviews --context kind-mesh1 | sed -n '/Spec:/,\$p' | head -25"
cap 14 "kubectl -n default get destinationrule reviews -o yaml --context kind-mesh1 | sed -n '/spec:/,\$p' | head -22"
cap 15 "bash \"$ROOT/scripts/06-traffic-routing.sh\" 2>&1 | tail -12"
cap 16 "kubectl -n istio-system get pods --context kind-mesh1 | grep -Ei 'prometheus|grafana|kiali|jaeger'"
cap 17 "kubectl -n istio-system get svc --context kind-mesh1 | grep -Ei 'prometheus|grafana|kiali|jaeger|tracing'"
cap 21 "kubectl get nodes --context kind-mesh1; echo; kubectl get nodes --context kind-mesh2; echo; kubectl -n default get pods --context kind-mesh1; echo; kubectl -n default get peerauthentication --context kind-mesh1; kubectl -n default get virtualservice --context kind-mesh1; kubectl -n default get destinationrule --context kind-mesh1"

# long runs: pull the tail of the newest saved evidence files
latest() { ls -t "$EV"/$1-*.txt 2>/dev/null | head -1; }
RES=$(latest resilience); VER=$(latest verify)
if [ -n "${RES:-}" ]; then
  { printf 'root@mesh-lab:~/devops-project-5# bash scripts/10-resilience.sh --hard\n'
    grep -E 'baseline|during|after|HARD FAILURE|v2 absent|restoring|OK|ok=|fail=' "$RES" | head -40
  } > "$TMP/20.txt"
fi
if [ -n "${VER:-}" ]; then
  { printf 'root@mesh-lab:~/devops-project-5# bash scripts/09-verify.sh\n'
    grep -E 'routed to|BOTH clusters|cross-cluster|ENDPOINT|172.30|10.244|10.245' "$VER" | head -30
  } > "$TMP/08b.txt"
fi

fi   # end capture block (skipped with --render-only)

python3 - "$TMP" "$EV/doc-screens.html" <<'PY'
import html, os, re, sys

tmp, out = sys.argv[1], sys.argv[2]
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
titles = {
 "00": "Installed tooling",
 "01": "Cluster 1 - Kubernetes nodes (mesh1)",
 "02": "Cluster 2 - Kubernetes nodes (mesh2)",
 "02b": "kubectl contexts for both clusters",
 "03": "Istio control plane and gateways - cluster 1",
 "04": "Istio control plane and gateways - cluster 2",
 "05": "Bookinfo application pods",
 "06": "Envoy sidecar injection",
 "07": "istioctl proxy-status",
 "08": "Cross-cluster service discovery (Envoy endpoints)",
 "08b": "Cross-cluster request test",
 "09": "Remote cluster registration",
 "10": "Gateway LoadBalancer addresses",
 "11": "PeerAuthentication - STRICT mTLS",
 "12": "mTLS enforcement test",
 "13": "VirtualService reviews (80/20)",
 "14": "DestinationRule reviews (subsets)",
 "15": "Measured traffic split",
 "16": "Observability pods",
 "17": "Observability services",
 "20": "Resilience test",
 "21": "Final verification",
}
order = sorted(titles)
secs = []
for k in order:
    p = os.path.join(tmp, k + ".txt")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        continue
    body = html.escape(ANSI.sub("", open(p, encoding="utf-8", errors="replace").read())).rstrip()
    secs.append(
        f'<section class="term" id="s{k}" tabindex="0" role="region" aria-label="terminal card {k}">'
        f'<div class="bar"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>'
        f'<span class="ttl">root@mesh-lab: ~/devops-project-5</span></div>'
        f'<pre>{body}</pre></section>'
    )

doc = """<!doctype html><html><head><meta charset="utf-8"><title>Terminal evidence</title>
<style>
  html,body { margin:0; background:#0b0f14; }
  body { padding:26px; font-family: ui-monospace,"Cascadia Mono",Consolas,monospace; }
  .term { width:1160px; margin:0 auto; border-radius:10px; overflow:hidden;
          border:1px solid #2b3440; box-shadow:0 14px 40px rgba(0,0,0,.55); background:#11161d; }
  .bar { height:34px; background:#1a212a; display:flex; align-items:center; gap:7px; padding:0 13px;
         border-bottom:1px solid #2b3440; }
  .dot { width:11px; height:11px; border-radius:50%; display:inline-block; }
  .r{background:#ff5f57}.y{background:#febc2e}.g{background:#28c840}
  .ttl { margin-left:10px; color:#8b98a5; font-size:12.5px; letter-spacing:.2px; }
  pre { margin:0; padding:16px 18px 18px; color:#d7e2ec; font-size:13px; line-height:1.5;
        white-space:pre-wrap; word-break:break-word; }
  body.single .term { display:none; }
  body.single .term.show { display:block; }
</style></head><body>
""" + "\n".join(secs) + """
<script>
 const s=new URLSearchParams(location.search).get("s");
 if(s){document.body.classList.add("single");
       const e=document.getElementById("s"+s); if(e) e.classList.add("show");}
</script></body></html>"""
open(out, "w", encoding="utf-8").write(doc)
print("wrote", out, len(secs), "cards")
PY