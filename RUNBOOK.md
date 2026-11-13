# RUNBOOK

Every command in order, with what you should see. Run everything from WSL.

---

## 0. Prerequisites (once)

**On Windows**, `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=9GB
processors=12
swap=6GB
```

Then `wsl --shutdown`.

**Inside WSL:**

```bash
wsl -d Ubuntu -u root -- bash scripts/01-wsl-preflight.sh
wsl -d Ubuntu -u root -- bash scripts/00-install-tools.sh
```

Expected: `jq`, `unzip`, `docker`, `kind`, `kubectl`, `istioctl` all report a
version. Anything "MISSING" means stop and fix it now.

**Keep the distro alive while you work.** WSL powers the VM off when the last
shell exits, which kills every container. Leave this running in its own window:

```bash
wsl -d Ubuntu -u root -- sleep infinity
```

Symptom if you skip it: clusters vanish with exit code 128 and
`systemd-logind: The system will power off now!` in the journal.

---

## 1. Two clusters

```bash
bash scripts/02-clusters-up.sh
```

Expected:

```
mesh1-control-plane   Ready   control-plane   v1.37.0   172.30.0.2
mesh2-control-plane   Ready   control-plane   v1.37.0   172.30.0.3
```

Two things this proves: two API servers, and two pod CIDRs
(`10.244.0.0/16` and `10.245.0.0/16`) with no route between them.

📸 Screenshot: both `kubectl get nodes -o wide` outputs.

---

## 2. The mesh

```bash
bash scripts/03-istio-multicluster.sh
```

Expected:
* `istioctl remote-clusters` lists the *other* cluster in each cluster
* both `istio-eastwestgateway` services have an external VIP from their pool
  (`172.30.0.200-209` and `172.30.0.210-219`)
* `istioctl proxy-status` shows `SYNCED` for the local gateways. In
  multi-primary, each control plane only reports **its own** proxies - seeing
  only mesh1 proxies from mesh1 is correct, not a fault. Cross-cluster
  endpoint sharing is what `remote-clusters` and the endpoint lists prove.

📸 Screenshot: `kubectl get pods -n istio-system` on both contexts, plus
`istioctl remote-clusters`.

---

## 3. Shared root of trust

```bash
bash scripts/03b-shared-ca.sh
```

**Do not skip this.** By default each istiod creates its own root CA, so a
certificate issued in mesh1 is not trusted in mesh2. The symptom is subtle:
in-cluster requests return 200, but any request that lands on a remote pod
fails with a TLS error. The script installs Istio's sample `cacerts` into both
clusters and restarts istiod and the workloads.

Expected: the `ROOTCA` line from `istioctl proxy-config secret` is identical in
both clusters.

📸 Screenshot: `istioctl proxy-config secret <pod>` from both clusters showing
the same root serial.

## 4. Sample application

```bash
bash scripts/04-bookinfo.sh
```

Expected: every pod is `2/2`, and:

```
productpage-v1-xxxx  : app=productpage  | init=istio-init istio-proxy
details-v1-xxxx      : app=details      | init=istio-init istio-proxy
reviews-v1-xxxx      : app=reviews      | init=istio-init istio-proxy
...
```

`istio-proxy` appears under **initContainers** with `restartPolicy: Always`:
Istio 1.32 injects the sidecar as a *native sidecar* (a Kubernetes 1.28+
feature), so it counts toward pod readiness but is not in `spec.containers`.
That is why `kubectl` says `2/2` while the container list shows only one app.

📸 Screenshot: the pods list **and** the sidecar jsonpath output.
📸 Screenshot: `curl -s http://172.30.0.200/productpage | head -20`

---

## 5. mTLS

```bash
bash scripts/05-mtls.sh
```

Expected:

```
in-mesh request  -> HTTP 200
plaintext request -> HTTP 000 (000/reset = rejected by STRICT)
```

That second line is the actual proof. A `PeerAuthentication` screenshot alone
only shows intent; the blocked plaintext request shows enforcement.

📸 Screenshot: `kubectl describe peerauthentication default -n default`
📸 Screenshot: the two test results

---

## 6. Traffic routing

```bash
bash scripts/06-traffic-routing.sh
```

Expected:

```
v1=79 v2=21 v3=0 fail=0
```

The exact numbers vary. What matters is that v1 and v2 both answer, v3 stays at
zero (the VirtualService does not route to it), and the ratio is near 80:20.

If every request returns 503 instead, the client pod is holding a certificate
from before the shared-CA step - delete it and re-run:

```bash
kubectl -n default delete pod traffic-client --context kind-mesh1
```

📸 Screenshot: `kubectl describe virtualservice reviews` (shows weights 80/20)
📸 Screenshot: the measurement line

---

## 7. Observability

```bash
bash scripts/07-addons.sh
bash scripts/08-generate-traffic.sh
```

Then, each in its own terminal (Ctrl-C to stop):

```bash
istioctl dashboard kiali      --context kind-mesh1
istioctl dashboard grafana    --context kind-mesh1
istioctl dashboard prometheus --context kind-mesh1
istioctl dashboard jaeger     --context kind-mesh1
```

In Kiali: **Graph → namespace `default`** and wait for the traffic animation.

📸 Screenshot: Kiali service graph with edges between productpage, reviews,
details and ratings.
📸 Screenshot: Grafana Istio Mesh dashboard.
📸 Screenshot: a Prometheus query result.
📸 Screenshot: a Jaeger trace with multiple spans.

---

## 8. Verification

```bash
bash scripts/09-verify.sh
```

Writes `evidence/verify-<timestamp>.txt` containing all of the above plus the
two things that actually matter:

**Cross-cluster endpoints, seen in the data plane.** `kubectl get endpoints`
only lists *local* pods - in a multi-network mesh Istio does not write remote
pod IPs into the Kubernetes Endpoints object. The remote cluster is represented
by its east-west gateway VIP on port 15443:

```
$ istioctl -n default proxy-config endpoint productpage-v1-xxxx \
    --cluster 'outbound|9080||reviews.default.svc.cluster.local'
ENDPOINT             STATUS   OUTLIER CHECK   CLUSTER
10.244.0.23:9080     HEALTHY  OK              outbound|9080||reviews...
10.244.0.24:9080     HEALTHY  OK              outbound|9080||reviews...
10.244.0.25:9080     HEALTHY  OK              outbound|9080||reviews...
172.30.0.211:15443   HEALTHY  OK              outbound|9080||reviews...
```

That `172.30.0.211:15443` entry is mesh2: every remote pod, reached through the
east-west gateway over SNI-routed TLS. If it is missing, the remote secret is
not syncing.

**Cross-cluster request** - requests from a mesh1 client served by pods in both
clusters, counted by the `podname` in each response:

```
routed to mesh1 pods: 24/60
routed to mesh2 pods: 36/60
requests from mesh1 were served by pods in BOTH clusters - cross-cluster routing works
```

📸 Screenshot: the Envoy endpoint list and that success line.

---

## 9. Resilience

```bash
bash scripts/10-resilience.sh          # soft failure (one cluster)
bash scripts/10-resilience.sh --hard   # hard failure (both clusters)
```

**Soft failure** - `reviews-v2` scaled to 0 in `mesh2` only. Measured:

```
baseline (both clusters up)        ok=30 fail=0
during  (mesh2 v2 scaled to 0)    ok=30 fail=0  v2_served=6
after   (mesh2 v2 restored)       ok=30 fail=0
```

Nothing failed, and v2 traffic kept flowing at ~20%. The 20% share was served
by `mesh1`'s `reviews-v2` pods: cross-cluster service discovery provided the
failover, not a hand-written policy. The pod list printed during the outage
proves the mesh2 v2 pod was gone while v2 responses continued.

**Hard failure** - `reviews-v2` scaled to 0 in **both** clusters. Now the 20%
share has no destination at all, requests for it fail, and the split recovers
once v2 is restored. That is the honest limit: connecting two clusters gives
you endpoint redundancy, but not automatic fallback to another *subset*
without `outlierDetection` or an explicit fallback route.

📸 Screenshot: `kubectl get pods -l app=reviews --context kind-mesh2` while
`reviews-v2` is at 0.
📸 Screenshot: the soft-failure result block (all `fail=0`).

---

## 10. Teardown

```bash
bash scripts/99-teardown.sh
```

Then `wsl --shutdown` from Windows to release the 9 GB.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `could not find a log line that matches "Reached target ... Multi-User System"` | inotify instances exhausted | `bash scripts/01-wsl-preflight.sh` |
| Containers exit with code 128, clusters vanish | WSL powered off between shells | run `wsl -d Ubuntu -u root -- sleep infinity` |
| `duplicate entries for key [name="PILOT_TRACE_SAMPLING"]` | `pilot.env` instead of `pilot.traceSampling` | already fixed in `03-istio-multicluster.sh` |
| east-west gateway has no VIP | MetalLB not advertising | `kubectl -n metallb-system get pods`, `kubectl get ipaddresspool -A` |
| `istioctl remote-clusters` lists nothing | remote secret server points at `127.0.0.1` | re-run `03-istio-multicluster.sh` (it uses `--server https://<node-ip>:6443`) |
| Bookinfo pods `1/1` | namespace not labelled before deploy | `kubectl rollout restart deploy -n default` |
| `/productpage` not reachable | gateway manifest missing | `04-bookinfo.sh` applies `bookinfo-gateway.yaml` |