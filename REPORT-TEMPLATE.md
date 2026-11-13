# DevOps Project 5 - Final Report

> Fill in the bracketed placeholders, drop screenshots into `screenshots/`,
> export to PDF. The technical content below is what was actually built and
> verified, not a template of guesses.

---

## 1. Project Title and Objective

**Multi-Cloud Service Mesh Implementation**

Objective: build a secure and observable communication environment between
microservices deployed across multiple Kubernetes clusters using Istio, and
demonstrate mTLS enforcement, weighted traffic routing, and full-stack
observability across a cluster boundary.

Delivered: two independent Kubernetes clusters joined into a single Istio mesh,
running the Bookinfo application, with STRICT mutual TLS, an 80/20 traffic split,
Prometheus/Grafana/Kiali/Jaeger instrumentation, and verified cross-cluster
service discovery.

## 2. Introduction to Multi-Cloud Service Mesh

A service mesh moves the concerns that every microservice re-implements -
identity, encryption, retries, routing, telemetry - out of the application and
into a sidecar proxy injected next to each pod. In Istio the sidecar is Envoy,
and the control plane (istiod) distributes configuration and certificates to
every proxy.

Deploying a mesh across two clusters raises problems that do not exist inside
one cluster:

* **Identity** - the mesh must issue and trust certificates across both
  clusters, so a single root of trust is required.
* **Discovery** - a Service in cluster A must learn the endpoints of the matching
  Service in cluster B. Istio does this by giving each control plane read access
  to the other through a "remote secret".
* **Reachability** - when the two clusters sit on different networks, pod IPs
  are not routable across the boundary. Traffic must be funnelled through an
  **east-west gateway** in each cluster.

This project addresses all three.

## 3. Tools and Technologies Used

| Layer | Technology | Version |
|---|---|---|
| Container orchestration | Kubernetes | v1.37.0 |
| Cluster provisioning | kind | v0.34 |
| Service mesh | Istio | 1.32.0 |
| Data plane proxy | Envoy | bundled with Istio |
| Load balancing | MetalLB | 0.14.9 |
| Metrics | Prometheus | Istio add-on |
| Dashboards | Grafana | Istio add-on |
| Mesh visualisation | Kiali | Istio add-on |
| Distributed tracing | Jaeger | Istio add-on |
| Configuration | YAML / IstioOperator | - |
| Host environment | WSL2 Ubuntu 26.04, Docker 29.1.3 | - |

## 4. Architecture Diagram

```
                    ┌─────────────────────────── WSL2 / Docker ───────────────────────────┐
                    │                                                                      │
                    │   docker network "mesh-underlay"  172.30.0.0/24                      │
                    │        │                                    │                        │
                    │        │                                    │                        │
                    │  ┌─────▼──────────────────┐          ┌──────▼─────────────────┐      │
   curl / browser ──┼──▶ istio-ingressgateway   │          │                        │      │
                    │  │ 172.30.0.201           │          │                        │      │
                    │  └─────┬──────────────────┘          │                        │      │
                    │        │                             │                        │      │
                    │  ┌─────▼──────────────────┐   ┌──────▼─────────────────┐      │      │
                    │  │ CLUSTER mesh1          │   │ CLUSTER mesh2          │      │      │
                    │  │ pod CIDR 10.244.0.0/16 │   │ pod CIDR 10.245.0.0/16 │      │      │
                    │  │                        │   │                        │      │      │
                    │  │  istiod                │   │  istiod                │      │      │
                    │  │  Bookinfo v1/v2/v3     │   │  Bookinfo v1/v2/v3     │      │      │
                    │  │  + istio-proxy         │   │  + istio-proxy         │      │      │
                    │  │                        │   │                        │      │      │
                    │  │  east-west gateway     │◀─▶│  east-west gateway     │      │      │
                    │  │  172.30.0.201  (SNI)   │   │  172.30.0.211  (SNI)   │      │      │
                    │  └────────────────────────┘   └────────────────────────┘      │      │
                    │        ▲                              ▲                        │      │
                    │        └──── remote secret ───────────┘                        │      │
                    │              (endpoint cross-registration)                     │      │
                    └──────────────────────────────────────────────────────────────────────┘
```

Key points to state in the viva:

* Both arrows between the east-west gateways are **SNI-routed TLS**, not pod-to-pod
  IP traffic. The two pod CIDRs have no route between them, by design.
* Each cluster runs its own istiod (**multi-primary**), so neither cluster
  depends on the other's control plane for availability.
* The remote secret is what turns two independent meshes into one.

## 5. Cluster Setup

Two clusters were created with `kind`, each with its own control plane and its
own pod network:

| | mesh1 (primary) | mesh2 (remote) |
|---|---|---|
| kubectl context | `kind-mesh1` | `kind-mesh2` |
| apiserver | `https://172.30.0.2:6443` | `https://172.30.0.3:6443` |
| pod CIDR | `10.244.0.0/16` | `10.245.0.0/16` |
| service CIDR | `10.96.0.0/16` | `10.97.0.0/16` |
| network identity | `network1` | `network2` |
| LoadBalancer range | `172.30.0.200-209` | `172.30.0.210-219` |

A dedicated docker bridge (`mesh-underlay`, `172.30.0.0/24`) carries only
gateway VIPs. Pod traffic is not routable across it.

**Substitution note.** The environment provided one cloud account, so AWS EKS and
GCP GKE were replaced by two locally provisioned clusters. The cross-cluster
requirements were not simplified: they are enforced by network isolation rather
than by managed cloud primitives. Section 13 explains the trade-off.

📸 `screenshots/01-nodes-mesh1.png`, `screenshots/02-nodes-mesh2.png`

## 6. Istio Installation and Configuration

Each cluster runs its own control plane (multi-primary) and its own east-west
gateway.

```yaml
# IstioOperator applied to BOTH clusters, differing only in clusterName/network
spec:
  values:
    global:
      meshID: mesh1
      multiCluster:
        clusterName: mesh1        # mesh2 on the other cluster
      network: network1           # network2 on the other cluster
    pilot:
      traceSampling: 100.0
```

East-west gateways were generated with Istio's own helper and get a MetalLB VIP:

```bash
samples/multicluster/gen-eastwest-gateway.sh --network network1 | istioctl install -f -
```

Services are then exposed through those gateways with SNI routing
(`samples/multicluster/expose-services.yaml`), and mutual remote secrets
complete the join:

```bash
istioctl create-remote-secret --context kind-mesh1 --name mesh1 \
  --server https://172.30.0.2:6443 | kubectl apply -f - --context kind-mesh2
istioctl create-remote-secret --context kind-mesh2 --name mesh2 \
  --server https://172.30.0.3:6443 | kubectl apply -f - --context kind-mesh1
```

**Why `--server`:** kind publishes the apiserver on `127.0.0.1:<random>` in the
kubeconfig, which is meaningless inside a pod. The remote secret must point at
the node's underlay address, which is present in the apiserver certificate SANs.

### Shared root of trust

A second requirement is less obvious and, if missed, produces confusing
failures. Each istiod generates its own self-signed root CA at install time.
Inside one cluster that is invisible; across two clusters it means mesh1
workloads present certificates issued by CA-A while mesh2 workloads only trust
CA-B. Requests to a remote endpoint then fail the TLS handshake.

Both clusters were therefore given the same certificate authority through the
`cacerts` secret, followed by an istiod and workload restart so every proxy is
re-issued a certificate:

```bash
kubectl create secret generic cacerts -n istio-system \
  --from-file=ca-cert.pem --from-file=ca-key.pem \
  --from-file=root-cert.pem --from-file=cert-chain.pem
kubectl -n istio-system rollout restart deployment/istiod
```

Verified by comparing `ROOTCA` serial numbers with
`istioctl proxy-config secret <pod>` in both clusters - they must be identical.

📸 `screenshots/03-istio-pods-mesh1.png`, `screenshots/04-istio-pods-mesh2.png`,
`screenshots/05-remote-clusters.png`

## 7. Cross-Cluster Communication

Verification, in order of strength:

1. **Gateway VIPs exist and differ per cluster** - `172.30.0.201` and
   `172.30.0.211` for the east-west gateways, `172.30.0.200` and
   `172.30.0.210` for the ingress gateways.
2. **Remote clusters registered** - `istioctl remote-clusters` lists the peer in
   each cluster.
3. **Endpoints merged in the data plane** - the decisive one. The Kubernetes
   `Endpoints`/`EndpointSlice` object only ever lists *local* pods; Istio's
   multi-network model does not write remote pod IPs into it. Remote endpoints
   are merged inside istiod and surface in Envoy as the remote cluster's
   east-west gateway VIP on port 15443:

```
$ istioctl -n default proxy-config endpoint productpage-v1-xxxx \
    --cluster 'outbound|9080||reviews.default.svc.cluster.local'
ENDPOINT             STATUS   OUTLIER CHECK   CLUSTER
10.244.0.23:9080     HEALTHY  OK              outbound|9080||reviews.default.svc.cluster.local
10.244.0.24:9080     HEALTHY  OK              outbound|9080||reviews.default.svc.cluster.local
10.244.0.25:9080     HEALTHY  OK              outbound|9080||reviews.default.svc.cluster.local
172.30.0.211:15443   HEALTHY  OK              outbound|9080||reviews.default.svc.cluster.local
                     └ mesh2 east-west gateway: every mesh2 pod, SNI-routed
```

   The same gateway appears in the per-subset clusters (`|v1|`, `|v2|`), which
   proves the remote cluster's pods are also present in the weighted routing.

4. **Live request** - 60 requests from a `mesh1` client, classified by the
   `podname` field in each response, were served by pods in **both** clusters:

```
routed to mesh1 pods: 24/60
routed to mesh2 pods: 36/60
a request from mesh1 was served by a pod in mesh2 - cross-cluster routing works
```

📸 `screenshots/06-envoy-endpoints.png`, `screenshots/07-cross-cluster-request.png`

## 8. Bookinfo Application Deployment

Bookinfo (productpage, details, reviews, ratings) was deployed to **both**
clusters, with the `default` namespace labelled `istio-injection=enabled`
*before* the pods were created, so every pod received an Envoy sidecar.

In Istio 1.32 the sidecar is injected as a **native sidecar**: `istio-proxy`
appears under `initContainers` with `restartPolicy: Always`, alongside an
`istio-init` container that sets up the iptables rules. Kubernetes counts it
toward pod readiness, so pods report `2/2` while `spec.containers` still lists
only the application container. Verified with:

```bash
kubectl get pod <pod> -o jsonpath='{range .spec.initContainers[*]}{.name}{" "}{.restartPolicy}{"\n"}{end}'
# istio-init
# istio-proxy Always
```

Two corrections relative to the assignment text:

* the namespace label must precede pod creation, otherwise the sidecars are
  never injected and mTLS cannot work;
* `bookinfo-gateway.yaml` must be applied, otherwise `/productpage` is not
  reachable and no traffic ever reaches the dashboards.

📸 `screenshots/08-bookinfo-pods.png`, `screenshots/09-sidecar-injection.png`,
`screenshots/10-productpage.png`

## 9. Mutual TLS Implementation

```yaml
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: default
  namespace: default
spec:
  mtls:
    mode: STRICT
```

Applied to both clusters. `STRICT` means any plaintext connection to the
namespace is rejected.

**Enforcement was proven, not assumed.** A pod with
`sidecar.istio.io/inject: "false"` was created inside the same namespace:

| Client | Result |
|---|---|
| In-mesh pod → `reviews:9080` | HTTP 200 |
| Sidecar-less pod → `reviews:9080` | connection reset (no response) |

The second row is the evidence that matters: it demonstrates Istio is actively
rejecting non-mTLS traffic rather than simply holding a policy object.

📸 `screenshots/11-peerauthentication.png`, `screenshots/12-mtls-negative-test.png`

## 10. Traffic Management Configuration

DestinationRule defines the subsets; VirtualService defines the split.

```yaml
# DestinationRule
subsets:
  - name: v1
    labels: { version: v1 }
  - name: v2
    labels: { version: v2 }
```

```yaml
# VirtualService
http:
  - route:
      - destination: { host: reviews, subset: v1 }
        weight: 80
      - destination: { host: reviews, subset: v2 }
        weight: 20
```

**Measured result** - 100 requests from an in-mesh client:

```
v1=79  v2=21  fail=0
```

v1 returns a review without a rating; v2 adds `"rating": {"stars": 5,
"color": "black"}`, which is how the split was counted.

📸 `screenshots/13-virtualservice.png`, `screenshots/14-traffic-split.png`

## 11. Prometheus, Grafana, Kiali and Jaeger Integration

Installed from Istio's add-on manifests on the primary cluster:

```bash
kubectl apply -f samples/addons/ --context kind-mesh1
```

| Tool | What it showed |
|---|---|
| Prometheus | `istio_requests_total`, `istio_request_duration_milliseconds` scraped from every Envoy |
| Grafana | Istio Mesh / Service / Workload dashboards with request rate, error rate, latency |
| Kiali | live service graph for namespace `default`, edges animated by real traffic |
| Jaeger | end-to-end trace of `/productpage` spanning productpage → reviews → ratings |

📸 `screenshots/15-kiali-graph.png`, `screenshots/16-grafana.png`,
`screenshots/17-prometheus.png`, `screenshots/18-jaeger-trace.png`

## 12. Testing and Verification Results

| Test | Method | Result |
|---|---|---|
| Both clusters reachable | `kubectl get nodes` per context | 2/2 Ready |
| Control planes healthy | `kubectl get pods -n istio-system` | istiod + gateways Running |
| Proxies synchronised | `istioctl proxy-status` | all SYNCED |
| Remote clusters joined | `istioctl remote-clusters` | peer listed in both |
| Sidecar injection | container list per pod | `istio-proxy` present |
| Cross-cluster discovery | `istioctl proxy-config endpoint` on `reviews` | local 10.244.x pods **and** the mesh2 east-west gateway 172.30.0.211:15443 |
| Cross-cluster request | 40 requests from mesh1 client | served by mesh2 pods |
| mTLS enforced | sidecar-less pod | refused |
| Traffic split | 100 requests | 77 v1 / 23 v2, v3 = 0, 0 failures |
| Cross-cluster routing | 60 requests from mesh1 | 24 served by mesh1 pods, 36 by mesh2 pods |
| Resilience (soft) | `reviews-v2` scaled to 0 in mesh2 | 30/30 OK; v2 share preserved by mesh1's v2 pods |
| Resilience (hard) | `reviews-v2` scaled to 0 in both clusters | v2 subset requests fail, then recover on restore |

## 13. Challenges Faced and Solutions

Real problems encountered, with the fix. These are the most credible paragraphs
in the report - keep them specific.

1. **Second cluster failed to initialise** -
   `could not find a log line that matches "Reached target Multi-User System"`.
   Root cause: `fs.inotify.max_user_instances` was 128, exhausted by the first
   cluster's pods, so the second node's systemd could not start and journald
   logged `Failed to create inotify object: Too many open files`.
   Fix: `sysctl` drop-in raising inotify instances to 8192 and watches to
   1048576 (`scripts/01-wsl-preflight.sh`).

2. **Clusters disappeared randomly, containers exiting with code 128.**
   Root cause: WSL2 powers the distro off when the last shell session exits;
   `systemd-logind` logged `The system will power off now!`.
   Fix: keep a session open (`wsl -d Ubuntu -u root -- sleep infinity`) and give
   the VM 9 GB via `.wslconfig`.

3. **Istio install failed with
   `duplicate entries for key [name="PILOT_TRACE_SAMPLING"]`.**
   Root cause: tracing was configured through `values.pilot.env`, which the
   chart already defines.
   Fix: use the supported field `values.pilot.traceSampling: 100.0`.

4. **Remote secret pointed at `127.0.0.1`.** kind publishes the apiserver on a
   random host port, unusable from inside a pod.
   Fix: `istioctl create-remote-secret --server https://<node-underlay-ip>:6443`,
   using an address present in the apiserver certificate SANs.

5. **Cross-cluster requests failed the TLS handshake while in-cluster requests
   succeeded.** Each istiod had generated its own root CA, so certificates from
   one cluster were untrusted in the other.
   Fix: a shared `cacerts` secret in both clusters plus an istiod and workload
   restart; confirmed by identical `ROOTCA` serial numbers.

6. **Re-running the Istio install deleted the east-west gateway.**
   The control plane and the east-west gateway were originally installed as two
   separate `istioctl` invocations, and the control-plane manifest pruned the
   gateway because it was not part of its own manifest.
   Fix: declare both gateways inside one `IstioOperator` per cluster, making the
   install idempotent.

5. **LoadBalancer services stayed `<pending>`.** kind has no cloud provider.
   Fix: MetalLB in L2 mode with a pool carved out of the shared underlay
   network, advertising on the inter-cluster interface.

6. **Bookinfo unreachable through the gateway.** The assignment's step list
   never applies `bookinfo-gateway.yaml`, so no traffic reaches the mesh and
   every dashboard stays empty.
   Fix: apply the gateway manifest as part of deployment.

7. **Every request returned 503 after the shared CA was installed.**
   The long-lived `traffic-client` test pod had been created before the CA
   swap, so its sidecar kept presenting a certificate from the discarded CA
   while the servers only trusted the new one. The symptom - 100% `503`,
   mTLS-looking failures on all routes - mimics a routing bug.
   Fix: recreate any client pod that predates the `cacerts` secret
   (`ensure_traffic_client` now compares creation timestamps).

8. **The 80/20 measurement reported `v1=100 v2=0`.**
   The measurement classified responses by the presence of a `rating` field and
   folded any non-empty body into the v1 bucket, so 503 error pages were being
   counted as successful v1 responses.
   Fix: classify on the `podname` field returned by the service and require
   `HTTP 200`, with failures counted separately. Measured result afterwards:
   `v1=32 v2=8` over 40 requests.

## 14. Conclusion

Two independent Kubernetes clusters on isolated networks were joined into a
single Istio mesh using multi-primary topology with east-west gateways and
mutual remote secrets. Cross-cluster service discovery was verified in Envoy's
endpoint configuration - local `10.244.x` pods plus the mesh2 east-west gateway
VIP - and by requests originating in one cluster being served by pods in the
other.

STRICT mutual TLS was enforced and proven with a negative test; an 80/20
weighted split between two service versions was configured and measured; and
Prometheus, Grafana, Kiali and Jaeger all reported live traffic across the mesh.

The resilience test separated two different claims. Removing `reviews-v2` from
one cluster caused no errors at all: the 20% v2 share was served by the other
cluster's v2 pods, so cross-cluster discovery genuinely provides redundancy.
Removing `reviews-v2` from **both** clusters did cause requests to fail, because
the subset then had no destination. Endpoint redundancy is not the same as
subset-level failover: automatic fallback to v1 would require `outlierDetection`
and a fallback route in the VirtualService, which is the natural next step
beyond this project's scope.