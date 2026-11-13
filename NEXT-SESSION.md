# Next session — pick up here

Paused 2026-11-12 evening. Everything runs **locally** (two kind clusters in WSL).
No AWS/EKS/GCP needed — the report already explains the substitution.

## What is already captured

`screenshots/`
* `15-kiali-service-graph.png` — Kiali, service graph, namespace `default` (7 service / 12 edge, ~1 rps, 99% success)
* `16-grafana-mesh-dashboard.png` — Grafana → Istio → Istio Mesh (2.2 req/s, 100% success, workload latency table)
* `17-prometheus-istio-requests.png` — PromQL `sum(rate(istio_requests_total[1m])) by (destination_service_name)` graph

`evidence/`
* `verify-20261112-165017.txt` — full 09-verify run (envoy endpoints, 24/60 vs 36/60 cross-cluster)
* `resilience-20261112-165649.txt` — soft + hard failure results

## What still needs a screenshot (one per doc section)

Terminal-style evidence (Activity 1 items 1–9, Activity 2 items 10–14, 19–21):

1. `kubectl get nodes -o wide` — mesh1 and mesh2
2. `kubectl get pods -n istio-system` — both clusters (istiod + both gateways)
3. `kubectl get pods -n default` — Bookinfo, all `2/2`
4. Sidecar proof: `-o custom-columns=...spec.initContainers[*].name` (native sidecar)
5. `istioctl proxy-status` — all SYNCED
6. **Cross-cluster endpoints** — `istioctl proxy-config endpoint <pp-pod> --cluster 'outbound|9080||reviews...'`
   must show `10.244.x` pods **and** `172.30.0.211:15443`
7. `istioctl remote-clusters` — peer registered in both
8. Gateway VIPs — `get svc istio-ingressgateway istio-eastwestgateway` both clusters
9. `kubectl get peerauthentication default -o yaml`
10. mTLS test — in-mesh `200` vs sidecar-less pod `000`
11. `kubectl describe virtualservice reviews` / `destinationrule reviews -o yaml`
12. Traffic split line — `v1=77 v2=23 v3=0 fail=0`
13. Resilience result block (already in `evidence/`)
14. 18-jaeger-trace.png — **still missing**

## Jaeger (state at pause)

Tracing was just fixed and is working:
* `meshConfig.extensionProviders` → `jaeger` (zipkin, `jaeger-collector.istio-system:9411`)
* `Telemetry/mesh-default` in `istio-system`, `randomSamplingPercentage: 100`
* Jaeger UI base path changed to `/` → UI is at **http://localhost:16686/** (not `/jaeger/ui/`)
* Services already seen in Jaeger: `productpage.default`, `reviews.default`, `details.default`,
  `ratings.default`, `istio-ingressgateway.istio-system`
* Jaeger uses `emptyDir` storage → traces vanish on pod restart. Generate traffic first, then
  screenshot immediately.
* Service names in the UI have the namespace suffix, e.g. `productpage.default`.

Still to fix in the repo so a rebuild reproduces tracing:
* `scripts/03-istio-multicluster.sh` — add under `spec:` a `meshConfig.extensionProviders` block
* `scripts/07-addons.sh` — apply the `Telemetry/mesh-default` CR after installing Jaeger
* `scripts/11-dashboards.sh` — Jaeger check path `/` (base path changed) and update the printed URLs
* `RUNBOOK.md` / `REPORT-TEMPLATE.md` — mention tracing setup + the 100% sampling

## WSL reliability note

Long `wsl` invocations intermittently fail with `Wsl/Service/0x8007274c` (WSAETIMEDOUT).
The VM itself stays up (uptime confirmed), so it is an interop timeout, not a crash.
Workaround: retry the same command 2–4 times, or launch long scripts detached:

```bash
wsl -d Ubuntu -u root -- bash /tmp/run-detached.sh /path/to/script.sh /tmp/script.log
# then read /tmp/script.log with a short command
```

Keep one shell alive (`wsl -d Ubuntu -u root -- sleep infinity`) or the distro shuts down
between calls and the clusters look dead.

## Restart checklist for tomorrow

```bash
wsl -d Ubuntu -u root          # or the sleep-infinity keepalive
docker ps                      # mesh1-control-plane, mesh2-control-plane should be Up
kubectl get nodes --context kind-mesh1 --context kind-mesh2
bash scripts/11-dashboards.sh  # Kiali 20001, Grafana 3000, Prometheus 9090, Jaeger 16686
bash scripts/12-traffic-loop.sh   # background traffic for the dashboards
bash scripts/13-evidence-html.sh  # builds evidence/terminal-evidence.html
```

If the clusters are gone: `bash scripts/01-kind-clusters.sh` … then 02 → 03 → 03b → 04 → 06 → 07.