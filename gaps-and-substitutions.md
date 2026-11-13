# Gaps and substitutions

Read this before writing the report. It says exactly what differs from the
assignment PDF, why, and how each requirement is still satisfied.

## The one real deviation

The PDF specifies **AWS EKS + Google Cloud GKE**. This implementation runs both
clusters locally (kind, inside WSL2 Ubuntu). There is no GCP account available,
and a second cloud cannot be simulated honestly.

Everything else in the PDF is implemented as written.

## Requirement-by-requirement mapping

The 16-row completion checklist on page 19:

| # | PDF requirement | How it is satisfied here |
|---|---|---|
| 1 | Create AWS EKS cluster | Kubernetes cluster `mesh1` - real control plane, real nodes, `kubectl` context `kind-mesh1`, apiserver at `172.30.0.2:6443` |
| 2 | Create Google Cloud GKE cluster | Kubernetes cluster `mesh2` - independent control plane, context `kind-mesh2`, apiserver at `172.30.0.3:6443`, pod CIDR `10.245.0.0/16` |
| 3 | Install and configure Istio | Istio 1.32.0, own istiod in each cluster, mesh ID `mesh1` |
| 4 | Configure cross-cluster communication | multi-primary, multi-network: network identities, two east-west gateways with MetalLB VIPs, mutual remote secrets |
| 5 | Deploy Bookinfo microservices | all four services, all three review versions, in **both** clusters |
| 6 | Verify Envoy sidecar injection | `2/2` pods, `istio-proxy` container shown via jsonpath, plus a deliberate sidecar-less control pod |
| 7 | Implement mutual TLS | `PeerAuthentication` `mode: STRICT` in both clusters, **plus a negative test** the PDF does not ask for |
| 8 | Configure VirtualService | `reviews` virtual service, 80/20 weights |
| 9 | Configure DestinationRule | `reviews` destination rule with `v1`/`v2`/`v3` subsets |
| 10 | Install Prometheus and Grafana | Istio's official add-on manifests |
| 11 | Configure Kiali | Istio add-on, live service graph |
| 12 | Configure Jaeger | Istio add-on, distributed traces |
| 13 | Generate and monitor application traffic | 100 requests through the ingress gateway, measured and observed in all four tools |
| 14 | Test cross-cluster connectivity | Envoy's `reviews` endpoint list contains local `10.244.x` pods plus the mesh2 east-west gateway VIP; a mesh1 client is served by pods in both clusters |
| 15 | Perform resilience testing | `reviews-v2` scaled to 0 in the remote cluster, baseline/during/after measured |
| 16 | Prepare and submit the final project report | 14-section outline from page 18 |

Items 3-16 are cloud-agnostic: they are Istio custom resources and `kubectl`
commands. Only items 1 and 2 name a cloud provider.

## Where this is actually *harder* than the PDF's version

Worth stating in the report, because it is true:

* **Two different networks is not simulated away.** Docker's iptables isolation
  drops traffic between the two bridges, so pods in `mesh1` genuinely cannot
  reach pods in `mesh2` by IP. The east-west gateways are doing the same job an
  AWS NLB does between two VPCs.
* **No managed control plane to lean on.** EKS and GKE provision, patch and
  expose the apiserver for you. Here the kubeadm control plane, the kubeconfig
  contexts, the apiserver SANs and the remote-secret server addresses all had to
  be handled explicitly - see the `--server https://<node-ip>:6443` flag in
  `03-istio-multicluster.sh`, which is a direct consequence of kind publishing
  the apiserver on `127.0.0.1`.
* **Load balancing is real, not a mock.** MetalLB assigns actual VIPs
  (`172.30.0.200`, `172.30.0.210`) that are reachable across the cluster
  boundary, which is what makes the east-west gateways meaningful.

## What to write in the report

Be explicit rather than quiet about it. Suggested wording:

> The project was implemented on two independent Kubernetes clusters
> provisioned locally with kind inside WSL2, instead of AWS EKS and Google GKE,
> because the available environment provided only one cloud account. The
> clusters run separate control planes on two isolated pod networks
> (`10.244.0.0/16` and `10.245.0.0/16`) with no route between them, so the
> cross-cluster requirements - network identity, east-west gateways, remote
> secrets, mutual TLS and cross-cluster service discovery - were implemented and
> verified identically to the cloud topology. Section 4 of this report explains
> the substitution and what would change on EKS/GKE.

That is honest, and it addresses the thing a reviewer will actually probe:
"did you really test cross-cluster communication, or just install Istio twice?"

## If a real EKS cluster is required later

The scripts were written against `kubectl --context`, so the EKS path is a
re-run rather than a rewrite:

1. `aws configure` (region `us-east-1`), `eksctl create cluster --name eks-mesh --region us-east-1 --nodes 2 --node-type t3.large`
2. set `CTX1=$(kubectl config get-contexts -o name | grep eks-mesh)`, `NAME1=eks-mesh`, `NET1=network1`
3. `bash scripts/03-istio-multicluster.sh` - the east-west gateway becomes an AWS NLB automatically; the `--server` flag is only needed for kind
4. `bash scripts/04-bookinfo.sh` onwards, unchanged

Cost: about $4.90/day for one cluster, and roughly $9.50/day for two. Delete the
clusters the same day. The $200 credit on this account covers a full rebuild
several times over.

## Known limitations to state in the report

* Kiali is installed on the primary cluster only, so the graph shows `mesh1`
  workloads directly; remote `mesh2` endpoints appear as backing endpoints
  rather than full nodes. Multi-cluster Kiali needs its own configuration.
* `STRICT` mTLS will block any plaintext health probe in the namespace. The
  Bookinfo manifests define no probes, so this does not bite here, but it is a
  real production caveat and the report should mention `portLevelMtls`.
* The resilience test removes a deployment, not a cluster or a region. Measured
  result: with `reviews-v2` gone from one cluster the split is preserved (the
  other cluster's v2 pods absorb it); with v2 gone from **both** clusters the
  subset has no destination and those requests fail. Failover between subsets is
  not automatic without `outlierDetection` / a fallback route.
* In multi-network mode remote pods are represented in Envoy as the remote
  east-west gateway VIP (`:15443`), not as individual pod IPs. That is the
  intended design, but it means `kubectl get endpoints` alone is *not* evidence
  of cross-cluster discovery - the `istioctl proxy-config endpoint` output is.
* The `traffic-client` test pod must be recreated whenever the shared CA changes,
  otherwise its sidecar presents an untrusted certificate and everything
  returns 503.