# Evidence checklist

Mapped to the two evidence lists in the assignment (page 9 for Activity 1,
page 18 for Activity 2). Tick these off as you capture them.

Screenshots live in `screenshots/` (create it). Command output also lands in
`evidence/verify-*.txt`, which you can attach as a text appendix.

## Activity 1 - infrastructure and mesh

| # | PDF requirement | Command to run before the screenshot | Captured |
|---|---|---|---|
| 1 | AWS EKS cluster created | `kubectl get nodes -o wide --context kind-mesh1` | ☐ |
| 2 | GCP GKE cluster created | `kubectl get nodes -o wide --context kind-mesh2` | ☐ |
| 3 | Nodes Ready | both commands above, `STATUS=Ready` | ☐ |
| 4 | Istio installed in both clusters | `kubectl get pods -n istio-system --context kind-mesh1` and `... mesh2` | ☐ |
| 5 | Istio system pods running | same, showing istiod + gateways `Running` | ☐ |
| 6 | Bookinfo pods running | `kubectl get pods -n default --context kind-mesh1` | ☐ |
| 7 | Envoy sidecar injection | `kubectl get pods -n default --context kind-mesh1 -o jsonpath='{range .items[*]}{.metadata.name}{" : "}{.spec.containers[*].name}{"\n"}{end}'` | ☐ |
| 8 | Istio proxy status | `istioctl proxy-status --context kind-mesh1` | ☐ |
| 9 | Cross-cluster service discovery | `istioctl -n default proxy-config endpoint <productpage-pod> --cluster 'outbound\|9080\|\|reviews.default.svc.cluster.local'` - must list local `10.244.x` pods **and** `172.30.0.211:15443` (the mesh2 east-west gateway) | ☐ |

Extra worth including (not in the PDF, but it is what makes item 9 credible):

| # | What | Command | Captured |
|---|---|---|---|
| 9b | East-west gateways with real VIPs | `kubectl get svc -n istio-system --context kind-mesh1 \| grep eastwest` (both contexts) | ☐ |
| 9c | Remote cluster registration | `istioctl remote-clusters --context kind-mesh1` and `... mesh2` | ☐ |

## Activity 2 - security, traffic, observability

| # | PDF requirement | Command to run before the screenshot | Captured |
|---|---|---|---|
| 10 | PeerAuthentication configuration | `kubectl describe peerauthentication default -n default --context kind-mesh1` | ☐ |
| 11 | mTLS actually enforced | output of `scripts/05-mtls.sh`: `200` in-mesh, `000` plaintext | ☐ |
| 12 | VirtualService configuration | `kubectl describe virtualservice reviews -n default --context kind-mesh1` | ☐ |
| 13 | DestinationRule configuration | `kubectl get destinationrule reviews -n default -o yaml --context kind-mesh1` | ☐ |
| 14 | Traffic split working | `v1=.. v2=..` line from `06-traffic-routing.sh` | ☐ |
| 15 | Kiali service graph | Kiali → Graph → namespace `default` | ☐ |
| 16 | Grafana dashboard | Grafana → Istio Mesh Dashboard | ☐ |
| 17 | Prometheus metrics | Prometheus → `istio_requests_total` query graph | ☐ |
| 18 | Jaeger distributed tracing | Jaeger → search service `productpage` → open a trace | ☐ |
| 19 | Proxy status, both clusters | `istioctl proxy-status` on each context | ☐ |
| 20 | Resilience test results | the baseline/during/after numbers from `10-resilience.sh` | ☐ |
| 21 | Cross-cluster connectivity | `09-verify.sh` section 9 and 10 | ☐ |

## Final submission pack

* [ ] `report.pdf` built from the 14-section outline in the PDF
* [ ] `yaml/` - peer-authentication, reviews-destination-rule, reviews-virtual-service
* [ ] `evidence/verify-*.txt`
* [ ] `screenshots/` with the images above
* [ ] this project folder zipped

## Two screenshots that carry the most weight

If anything gets questioned, these are the two that prove the project is real:

1. **`istioctl proxy-config endpoint`** for `reviews`, showing the local
   `10.244.x` pods **and** `172.30.0.211:15443` - mesh2's east-west gateway.
   That second entry can only exist if the remote secret is synced and the
   east-west gateways are working. (Use Envoy's view, not
   `kubectl get endpoints`: in a multi-network mesh the Kubernetes Endpoints
   object only ever holds local pod IPs.)
2. **The mTLS negative test**, where the sidecar-less pod is refused. This
   proves `STRICT` is enforced rather than merely declared.